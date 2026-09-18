"""Multi-Agent Debate & Consensus.

For hard or ambiguous questions, a single tutor answer can hide nuance or
propagate a subtle error. This module orchestrates a structured debate
between two adversarial LLM personas and a neutral judge:

    1. Proponent  - argues the most likely / textbook-standard position.
    2. Skeptic    - challenges it, surfaces edge cases, alternative views,
                    and common misconceptions.
    3. (optional multi-round rebuttal)
    4. Judge      - synthesises a balanced, evidence-grounded consensus and
                    assigns a confidence level.

Grounded in the student's course material via RAG so the debate stays
faithful to the syllabus rather than hallucinating.
"""

from typing import AsyncGenerator

import structlog
import google.generativeai as genai

from app.services.llm import get_gemini_model
from app.rag.retriever import retrieve

logger = structlog.get_logger()


PROPONENT_PROMPT = """You are the PROPONENT in an academic debate about a student's question for the subject "{subject}".

Your role: present the clearest, most widely-accepted answer. Be rigorous and cite reasoning. Use the course material below when relevant.

{context}

Question: {question}

Give your position in 3-5 concise sentences. Be confident but precise."""


SKEPTIC_PROMPT = """You are the SKEPTIC in an academic debate about a student's question for the subject "{subject}".

Your role: critically examine the Proponent's answer. Point out edge cases, common misconceptions, oversimplifications, alternative interpretations, or conditions under which it fails. Use the course material below when relevant. Do NOT be contrarian for its own sake - be intellectually honest.

{context}

Question: {question}

Proponent's position:
{proponent}

Give your critique in 3-5 concise sentences."""


JUDGE_PROMPT = """You are the JUDGE of an academic debate for the subject "{subject}". You are neutral, precise, and pedagogical.

Synthesise the debate into a single balanced answer for the student. Resolve the disagreement, keep what is correct from both sides, and explicitly note any remaining nuance or conditions. End with a one-line "Confidence: High/Medium/Low" rating.

{context}

Question: {question}

Proponent:
{proponent}

Skeptic:
{skeptic}

Write the consensus answer for the student (4-7 sentences), then the confidence line."""


PEER_JUDGE_PROMPT = """You are moderating a debate between two students on the topic below, for the subject "{subject}". You are an encouraging but rigorous AI moderator.

{context}

Topic / Question: {topic}

{arguments_text}

Write a moderation verdict that:
1. Names one clear strength in EACH student's argument (be specific, quote a phrase if useful).
2. Identifies which position is better supported by the course material and reasoning, or says it's a genuine tie.
3. Notes anything either side got factually wrong or oversimplified, grounded in the course material above if provided.
4. Ends with a one-line "Confidence: High/Medium/Low" rating.
Keep it to 5-8 sentences, addressed to both students by name where given."""


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    text = "\n--- Course Material ---\n"
    for i, c in enumerate(chunks, 1):
        src = c.get("source_file", "unknown")
        page = c.get("page", "?")
        text += f"[{i}] ({src} p.{page}) {c.get('text', '')[:600]}\n"
    text += "--- End Material ---\n"
    return text


async def _generate(prompt: str, temperature: float = 0.7) -> str:
    model = get_gemini_model()
    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature, max_output_tokens=2048
            ),
        )
        return resp.text.strip()
    except Exception as e:  # pragma: no cover - network failure path
        logger.error("debate_generate_failed", error=str(e))
        return "(This debater was unable to respond due to an error.)"


async def run_debate_stream(
    question: str,
    subject_code: str | None = None,
    subject_name: str | None = None,
    rounds: int = 1,
) -> AsyncGenerator[tuple[str, dict], None]:
    """Yield (event_type, data) tuples for a full debate.

    Event types: debate_start, turn_start, turn, turn_end, done.
    """
    subject = subject_name or "this subject"
    context_chunks: list[dict] = []
    if subject_code:
        try:
            context_chunks = retrieve(question, subject_code, top_k=4)
        except Exception as e:
            logger.warning("debate_rag_failed", error=str(e))
    context = _format_context(context_chunks)

    yield ("debate_start", {
        "question": question,
        "subject": subject,
        "rag_sources": [
            {"source_file": c.get("source_file", ""), "page": c.get("page", 0)}
            for c in context_chunks
        ],
    })

    # Round 1: Proponent
    yield ("turn_start", {"role": "proponent", "label": "Proponent"})
    proponent = await _generate(
        PROPONENT_PROMPT.format(subject=subject, context=context, question=question),
        temperature=0.6,
    )
    yield ("turn", {"role": "proponent", "label": "Proponent", "content": proponent})

    # Skeptic
    yield ("turn_start", {"role": "skeptic", "label": "Skeptic"})
    skeptic = await _generate(
        SKEPTIC_PROMPT.format(
            subject=subject, context=context, question=question, proponent=proponent
        ),
        temperature=0.8,
    )
    yield ("turn", {"role": "skeptic", "label": "Skeptic", "content": skeptic})

    # Optional extra rebuttal rounds
    for r in range(max(0, rounds - 1)):
        yield ("turn_start", {"role": "proponent", "label": "Proponent (rebuttal)"})
        rebuttal_prompt = (
            f"{PROPONENT_PROMPT.format(subject=subject, context=context, question=question)}\n\n"
            f"The Skeptic argued:\n{skeptic}\n\nRespond to the Skeptic's critique in 2-4 sentences."
        )
        proponent = await _generate(rebuttal_prompt, temperature=0.6)
        yield ("turn", {"role": "proponent", "label": "Proponent (rebuttal)", "content": proponent})

    # Judge
    yield ("turn_start", {"role": "judge", "label": "Judge — Consensus"})
    judge = await _generate(
        JUDGE_PROMPT.format(
            subject=subject, context=context, question=question,
            proponent=proponent, skeptic=skeptic,
        ),
        temperature=0.4,
    )
    yield ("turn", {"role": "judge", "label": "Judge — Consensus", "content": judge})

    yield ("done", {"consensus": judge})


async def judge_peer_debate(
    topic: str,
    arguments: list[dict],
    subject_code: str | None = None,
    subject_name: str | None = None,
) -> str:
    """AI-moderated verdict for a two-(or-more)-student peer debate.

    `arguments` is a list of {"name": str, "content": str} - one per student
    who has submitted a position on `topic`. Unlike run_debate_stream (which
    pits two AI personas against each other), both sides here are written by
    real students; the AI's only role is neutral moderation.
    """
    subject = subject_name or "this subject"
    context_chunks: list[dict] = []
    if subject_code:
        try:
            context_chunks = retrieve(topic, subject_code, top_k=4)
        except Exception as e:
            logger.warning("peer_debate_rag_failed", error=str(e))
    context = _format_context(context_chunks)

    arguments_text = "\n\n".join(
        f"{a.get('name', 'A student')}'s position:\n{a.get('content', '')}"
        for a in arguments
    )

    return await _generate(
        PEER_JUDGE_PROMPT.format(
            subject=subject, context=context, topic=topic,
            arguments_text=arguments_text,
        ),
        temperature=0.4,
    )
