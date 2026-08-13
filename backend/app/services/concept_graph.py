import json
import re
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept, ConceptPrerequisite
from app.models.subject import Subject
from app.services.llm import get_gemini_model
import google.generativeai as genai

logger = structlog.get_logger()

CONCEPT_EXTRACTION_PROMPT = """You are an expert curriculum designer. Given the following syllabus for the subject "{subject_name}", extract the distinct concepts/topics.

For each concept, provide:
1. name: A concise concept name (max 5 words)
2. description: ONE short sentence, max 15 words
3. difficulty_tier: 1 (foundational), 2 (intermediate), or 3 (advanced)
4. chapter: Which chapter/module it belongs to
5. prerequisites: List of other concept names from this list that must be understood first

Extract at most {max_concepts} concepts. Keep descriptions terse — the response must be complete valid JSON, never truncated.

Return ONLY a JSON array with no extra text. Example:
[
  {{"name": "Variables", "description": "Named storage locations in memory", "difficulty_tier": 1, "chapter": "Chapter 1", "prerequisites": []}},
  {{"name": "Functions", "description": "Reusable blocks of code", "difficulty_tier": 1, "chapter": "Chapter 2", "prerequisites": ["Variables"]}}
]

Syllabus:
{syllabus_text}"""

# Enough headroom for MAX_CONCEPTS terse entries plus any model preamble.
CONCEPT_OUTPUT_TOKENS = 16384
MAX_CONCEPTS = 40


def _parse_concept_json(raw_text: str) -> list[dict]:
    """Parse the model's JSON array, salvaging a response cut off by the token limit.

    A truncated response is still valid up to its last complete object, so rather
    than losing every concept we close the array after the last one.
    """
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()

    start = text.find("[")
    if start > 0:
        text = text[start:]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    last_complete = text.rfind("}")
    if last_complete == -1:
        raise ValueError("Failed to parse concept extraction response as JSON")

    try:
        concepts = json.loads(text[: last_complete + 1] + "]")
    except json.JSONDecodeError:
        raise ValueError("Failed to parse concept extraction response as JSON")

    logger.warning("concept_extraction_truncated_recovered", recovered=len(concepts))
    return concepts


async def extract_concepts_from_syllabus(
    db: AsyncSession, subject_id, syllabus_text: str
) -> list[dict]:
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise ValueError("Subject not found")

    model = get_gemini_model()
    prompt = CONCEPT_EXTRACTION_PROMPT.format(
        subject_name=subject.name,
        syllabus_text=syllabus_text,
        max_concepts=MAX_CONCEPTS,
    )

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.3,
            max_output_tokens=CONCEPT_OUTPUT_TOKENS,
        ),
    )

    try:
        concepts_data = _parse_concept_json(response.text)
    except ValueError:
        logger.error(
            "concept_extraction_json_parse_error", raw=response.text.strip()[:500]
        )
        raise

    # Insert concepts into DB
    concepts_data = [
        c for c in concepts_data if isinstance(c, dict) and c.get("name")
    ]
    name_to_concept = {}
    for c_data in concepts_data:
        existing = await db.execute(
            select(Concept).where(
                Concept.subject_id == subject_id,
                Concept.name == c_data["name"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        concept = Concept(
            subject_id=subject_id,
            name=c_data["name"],
            description=c_data.get("description"),
            difficulty_tier=c_data.get("difficulty_tier", 1),
            chapter=c_data.get("chapter"),
        )
        db.add(concept)
        await db.flush()
        name_to_concept[c_data["name"]] = concept

    await db.flush()

    # Reload all concepts for this subject to resolve prerequisite names
    result = await db.execute(
        select(Concept).where(Concept.subject_id == subject_id)
    )
    all_concepts = {c.name: c for c in result.scalars().all()}

    # Insert prerequisite edges
    for c_data in concepts_data:
        concept = all_concepts.get(c_data["name"])
        if not concept:
            continue
        for prereq_name in c_data.get("prerequisites", []):
            prereq = all_concepts.get(prereq_name)
            if prereq and prereq.id != concept.id:
                existing_edge = await db.execute(
                    select(ConceptPrerequisite).where(
                        ConceptPrerequisite.concept_id == concept.id,
                        ConceptPrerequisite.prerequisite_id == prereq.id,
                    )
                )
                if not existing_edge.scalar_one_or_none():
                    edge = ConceptPrerequisite(
                        concept_id=concept.id,
                        prerequisite_id=prereq.id,
                        strength=1.0,
                    )
                    db.add(edge)

    await db.commit()

    logger.info(
        "concepts_populated",
        subject=subject.code,
        count=len(concepts_data),
    )

    return concepts_data


DEPENDENCY_DETECTION_PROMPT = """You are an expert curriculum analyst. Given these text chunks from a course PDF, identify concept dependency relationships.

For each dependency, provide the prerequisite concept and the dependent concept.
Only include dependencies where understanding the prerequisite is clearly needed for the dependent concept.

Existing concepts in this course: {existing_concepts}

Text from course material:
{content_text}

Return ONLY a JSON array of dependency edges:
[
  {{"prerequisite": "Concept A", "dependent": "Concept B", "reason": "B requires understanding of A because..."}},
  ...
]"""


async def auto_detect_dependencies(
    db: AsyncSession, subject_id, content_chunks: list[str]
) -> list[dict]:
    """Auto-detect concept dependencies from PDF content using LLM."""
    # Get existing concepts
    result = await db.execute(
        select(Concept).where(Concept.subject_id == subject_id)
    )
    concepts = result.scalars().all()
    concept_names = [c.name for c in concepts]
    name_to_concept = {c.name: c for c in concepts}

    if not concept_names:
        return []

    # Use up to 5 chunks of content
    content_text = "\n\n".join(chunk[:1000] for chunk in content_chunks[:5])

    model = get_gemini_model()
    prompt = DEPENDENCY_DETECTION_PROMPT.format(
        existing_concepts=", ".join(concept_names),
        content_text=content_text,
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.2, max_output_tokens=CONCEPT_OUTPUT_TOKENS
            ),
        )
        edges_data = _parse_concept_json(response.text)
    except Exception as e:
        logger.error("dependency_detection_failed", error=str(e))
        return []

    added = []
    for edge in edges_data:
        prereq = name_to_concept.get(edge.get("prerequisite"))
        dependent = name_to_concept.get(edge.get("dependent"))
        if not prereq or not dependent or prereq.id == dependent.id:
            continue

        # Check if edge already exists
        existing = await db.execute(
            select(ConceptPrerequisite).where(
                ConceptPrerequisite.concept_id == dependent.id,
                ConceptPrerequisite.prerequisite_id == prereq.id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        new_edge = ConceptPrerequisite(
            concept_id=dependent.id,
            prerequisite_id=prereq.id,
            strength=1.0,
        )
        db.add(new_edge)
        added.append({
            "prerequisite": prereq.name,
            "dependent": dependent.name,
            "reason": edge.get("reason", ""),
        })

    if added:
        await db.commit()
        logger.info("dependencies_auto_detected", count=len(added), subject_id=str(subject_id))

    return added
