import re

import structlog

from app.agents.base import BaseAgent, match_concepts_in_text, GROUNDING_INSTRUCTION, grounding_note
from app.agents.state import AgentState
from app.rag.retriever import retrieve

logger = structlog.get_logger()

CRITIQUE_SYSTEM_PROMPT = """You are an academic writing tutor and assignment reviewer for {subject_name}.

When a student submits text for review, provide a thorough critique covering:

1. STRUCTURE ANALYSIS:
   - Does it have a clear introduction, body, and conclusion?
   - Is the argument logically structured?
   - Are paragraphs well-organised with topic sentences?

2. CONTENT ACCURACY:
   - Check claims against the course material provided
   - Flag any factual errors or misconceptions
   - Note where citations/references are needed but missing
   - Identify claims that are well-supported vs unsupported

3. DEPTH OF ANALYSIS:
   - Surface-level description vs deep analysis
   - Are concepts merely stated or actually explained and applied?
   - Are counterarguments considered?

4. TECHNICAL WRITING QUALITY:
   - Clarity and conciseness
   - Appropriate use of technical terminology
   - Grammar and style (academic register)

5. RUBRIC SCORING:
   Rate each dimension on a scale of 1-10:
   - Content Accuracy: [score]/10
   - Depth of Analysis: [score]/10
   - Structure & Organisation: [score]/10
   - Technical Writing: [score]/10
   - Use of Evidence: [score]/10
   - Overall: [weighted_average]/10

Course material for fact-checking:
{rag_context}

IMPORTANT:
- Be specific in your feedback — quote the student's text when pointing out issues
- Provide concrete suggestions for improvement, not just criticism
- Use a supportive, constructive tone
- If the text is a code explanation, also evaluate the technical accuracy of the code discussion

FORMAT YOUR RESPONSE AS:
## Assignment Critique

### Rubric Scores
| Dimension | Score | Comment |
|-----------|-------|---------|
| Content Accuracy | [x]/10 | [brief] |
| Depth of Analysis | [x]/10 | [brief] |
| Structure | [x]/10 | [brief] |
| Technical Writing | [x]/10 | [brief] |
| Use of Evidence | [x]/10 | [brief] |
| **Overall** | **[x]/10** | |

### Strengths
- [specific things done well]

### Areas for Improvement

#### Section-by-Section Feedback
**[Section/Paragraph identifier]**
> [Quoted student text]
[Your feedback]

### Specific Suggestions
1. [actionable suggestion]
2. [actionable suggestion]

### Missing References
- [Topic X] — consider citing [relevant concept from course material]"""


class CritiqueAgent(BaseAgent):
    name = "critique"

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        if not subject_code:
            return []

        messages = state.get("messages", [])
        if not messages:
            return []

        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        # Extract key terms from the essay for targeted RAG
        # Use first 500 chars to identify key topics
        text_excerpt = user_message[:500]
        query = f"Key topics: {text_excerpt}"
        chunks = retrieve(query, subject_code, top_k=6)

        # Also search for any specific terms that look like concept names
        words = set(user_message.split())
        if len(words) > 20:
            # This is likely an essay — search for main themes
            additional_query = " ".join(list(words)[:30])
            more_chunks = retrieve(additional_query, subject_code, top_k=3)
            # Deduplicate
            seen_texts = {c["text"][:100] for c in chunks}
            for c in more_chunks:
                if c["text"][:100] not in seen_texts:
                    chunks.append(c)
                    seen_texts.add(c["text"][:100])

        return chunks[:8]

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        from app.services.llm_provider import get_llm_provider

        subject_name = state.get("subject_name", "the subject")

        context_text = ""
        if context:
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"

        system_prompt = CRITIQUE_SYSTEM_PROMPT.format(
            subject_name=subject_name,
            rag_context=context_text or "No course material available for fact-checking.",
        )

        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        full_prompt = (
            f"{system_prompt}{GROUNDING_INSTRUCTION}\n\n--- Student's Submission ---\n"
            f"{user_message}\n--- End Submission ---"
        )

        provider = get_llm_provider()
        try:
            response = provider.generate(full_prompt, temperature=0.5, max_tokens=4096)
            note = grounding_note(context, response)
            return response + note if note else response
        except Exception as e:
            logger.error("critique_reason_failed", provider=provider.name, error=str(e))
            return "I apologize, but I encountered an error reviewing your submission. Please try again."

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        # Extract overall score from rubric
        overall_match = re.search(r"\*\*Overall\*\*\s*\|\s*\*\*(\d+)/10\*\*", response)
        if not overall_match:
            overall_match = re.search(r"Overall[^\d]*(\d+)/10", response)

        if not overall_match:
            return []

        score = int(overall_match.group(1))

        # Map score to quality
        if score >= 9:
            quality = 5
        elif score >= 7:
            quality = 4
        elif score >= 5:
            quality = 3
        elif score >= 3:
            quality = 2
        else:
            quality = 1

        # Try to identify which concepts the essay covers
        student_state = state.get("student_state", {})
        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        concept_ids = match_concepts_in_text(user_message, student_state, limit=10)
        if not concept_ids:
            return []

        # Report coverage too, so a critique session shows up in activity
        # analytics instead of looking like nothing was studied.
        state["concept_ids_touched"] = concept_ids
        return [{"concept_id": cid, "quality": quality} for cid in concept_ids]
