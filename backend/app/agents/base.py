import re
from typing import AsyncGenerator

import structlog
import google.generativeai as genai

from app.agents.state import AgentState
from app.services.llm import get_gemini_model
from app.services.llm_provider import get_llm_provider
from app.config import get_settings
from app.rag.retriever import retrieve

logger = structlog.get_logger()
settings = get_settings()

# Phrases that already signal the model is hedging/refusing rather than
# asserting unsupported facts - if present, we don't pile an extra caveat on.
_HEDGE_MARKERS = (
    "don't have enough information",
    "do not have enough information",
    "not covered in the",
    "isn't covered in",
    "is not covered in",
    "can't find this in",
    "cannot find this in",
    "no relevant material",
    "confidence note",
    "not in your course material",
    "not in the provided material",
)

GROUNDING_INSTRUCTION = (
    "\n\n--- Grounding Rules (follow strictly) ---\n"
    "1. Prefer the Retrieved Context above general knowledge when they overlap; "
    "if the context contradicts your general knowledge, trust the context - it "
    "is the student's actual course material.\n"
    "2. If the Retrieved Context is empty or does not contain enough information "
    "to answer confidently, say so explicitly (e.g. \"Your uploaded material "
    "doesn't cover this\") instead of inventing specifics.\n"
    "3. Never fabricate exact numbers, dates, citations, formulas, or quotations "
    "that do not appear in the Retrieved Context or conversation history - "
    "general, well-established facts are fine, but precise-sounding details "
    "that you are not actually sure of are not.\n"
    "--- End Grounding Rules ---\n"
)


def grounding_note(context: list[dict], response: str, min_score: float | None = None) -> str | None:
    """Return a caveat to append when a subject-grounded answer looks weakly sourced.

    Two independent signals, either being true is enough to add the caveat:
    (a) retrieval genuinely found nothing relevant (empty context / all scores
        below threshold) while the response reads as a confident, unhedged
        answer, or (b) the response shares almost no vocabulary with the
        retrieved chunks, suggesting the model drifted away from the source
        material despite it being available. This is a lightweight lexical
        check, not a full fact-checker - it catches gross hallucination risk,
        not subtle errors.
    """
    if not response or any(m in response.lower() for m in _HEDGE_MARKERS):
        return None

    if not context:
        return None  # no subject material at all (e.g. general chit-chat); not our call to flag

    min_score = settings.RAG_MIN_GROUNDING_SCORE if min_score is None else min_score
    best_score = max((c.get("score") or 0.0 for c in context), default=0.0)
    if best_score < min_score:
        return (
            "\n\n_Confidence note: this answer is only weakly supported by your "
            "uploaded course material (best match score "
            f"{best_score:.2f}). Treat specifics with caution and consider "
            "asking your instructor or checking a primary source._"
        )

    context_text = " ".join(c.get("text", "") for c in context).lower()
    context_words = set(re.findall(r"[a-z]{4,}", context_text))
    response_words = set(re.findall(r"[a-z]{4,}", response.lower()))
    if context_words and response_words:
        overlap = len(context_words & response_words) / max(1, len(response_words))
        if overlap < 0.08:
            return (
                "\n\n_Confidence note: this answer doesn't closely match the "
                "retrieved course material - double-check the specifics before "
                "relying on them._"
            )
    return None


def match_concepts_in_text(
    text: str, student_state: dict, limit: int = 3
) -> list[str]:
    """Concept ids whose names appear in the given text, longest name first.

    Used to attribute an assessment to the concepts a question actually covered,
    so mastery moves on the right rows rather than on an arbitrary selection.
    """
    if not text:
        return []

    lowered = text.lower()
    matches = [
        (cid, cdata.get("concept_name", ""))
        for cid, cdata in student_state.items()
        if cdata.get("concept_name") and cdata["concept_name"].lower() in lowered
    ]
    # Prefer the most specific name when several overlap ("Paging" vs "Demand Paging")
    matches.sort(key=lambda pair: len(pair[1]), reverse=True)
    return [cid for cid, _ in matches[:limit]]


async def grade_answer(
    question: str, answer: str, ground_truth: str = ""
) -> int | None:
    """Score a student's answer 1-5 with the LLM, or None if it could not be graded.

    Returning None rather than a default keeps an un-gradeable turn from being
    recorded as if it were real evidence of understanding.
    """
    prompt = (
        "You are grading a student's spoken exam answer.\n\n"
        f"Question asked:\n{question[-800:]}\n\n"
        f"Student's answer:\n{answer}\n\n"
    )
    if ground_truth:
        prompt += f"Reference material:\n{ground_truth}\n\n"
    prompt += (
        "Rate the answer on a scale of 1-5:\n"
        "1 = Completely wrong or off-topic\n"
        "2 = Mostly incorrect with a few relevant points\n"
        "3 = Roughly correct but superficial or incomplete\n"
        "4 = Correct with good understanding, minor gaps\n"
        "5 = Excellent, thorough and precise\n\n"
        "Respond with ONLY a single integer (1-5), nothing else."
    )

    try:
        model = get_gemini_model()
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.0, max_output_tokens=256
            ),
        )
        digits = re.search(r"[1-5]", resp.text or "")
        return int(digits.group()) if digits else None
    except Exception as e:
        logger.warning("answer_grading_failed", error=str(e))
        return None


def describe_llm_error(error: Exception) -> str:
    """Turn an LLM failure into something a student can act on.

    A rate-limit is the common case on the free tier and is worth naming, since
    "try again" is genuinely the right advice — unlike a generic failure.
    """
    text = str(error)
    if "429" in text or "quota" in text.lower():
        return (
            "I've hit the AI provider's rate limit for the moment. "
            "Please wait about a minute and ask again."
        )
    return "I apologize, but I encountered an error while processing your request. Please try again."


class BaseAgent:
    name: str = "base"
    system_prompt: str = "You are a helpful educational assistant."

    async def run(self, state: AgentState) -> AgentState:
        context = await self.retrieve_context(state)
        response = await self.reason(state, context)
        updates = await self.assess_understanding(state, response)

        state["rag_context"] = context
        state["concept_updates"] = updates
        state["active_agent"] = self.name
        state["response"] = response

        metadata = state.get("metadata", {})
        metadata["agent"] = self.name
        metadata["rag_sources"] = [
            {
                "source_file": c.get("source_file", ""),
                "page": c.get("page", 0),
                "score": c.get("score", 0),
            }
            for c in context
        ]
        state["metadata"] = metadata

        return state

    async def run_streaming(
        self, state: AgentState
    ) -> AsyncGenerator[tuple[str, dict], None]:
        # 1. Retrieve context
        context = await self.retrieve_context(state)
        state["rag_context"] = context
        state["active_agent"] = self.name

        metadata = state.get("metadata", {})
        metadata["agent"] = self.name

        # Yield agent_start
        yield ("agent_start", {"agent": self.name, "intent": state.get("intent", "")})

        # Yield rag_results
        rag_sources = [
            {
                "source_file": c.get("source_file", ""),
                "page": c.get("page", 0),
                "score": c.get("score", 0),
            }
            for c in context
        ]
        metadata["rag_sources"] = rag_sources
        yield ("rag_results", {"sources": rag_sources})

        # 2. Stream reasoning
        full_response = ""
        async for token in self._reason_stream(state, context):
            full_response += token
            yield ("token", {"content": token})

        state["response"] = full_response

        # 3. Assess understanding
        updates = await self.assess_understanding(state, full_response)
        state["concept_updates"] = updates

        # Yield concept updates
        for update in updates:
            yield ("concept_update", update)

        # Report which concepts this turn actually engaged with, so activity
        # analytics reflect real coverage rather than staying at zero.
        student_state = state.get("student_state", {})
        touched_names = [
            student_state[cid]["concept_name"]
            for cid in state.get("concept_ids_touched", [])
            if cid in student_state
        ]
        if touched_names:
            metadata["concepts_touched"] = touched_names
            yield ("concepts_touched", {"concepts": touched_names})

        metadata["concept_updates"] = updates
        state["metadata"] = metadata

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        if not subject_code:
            return []

        messages = state.get("messages", [])
        if not messages:
            return []

        query = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")
        return retrieve(query, subject_code, top_k=5)

    def _build_full_prompt(self, state: AgentState, context: list[dict]) -> str:
        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        context_text = ""
        if context:
            context_text = "\n\n--- Retrieved Context ---\n"
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"
            context_text += "\n--- End Context ---\n"

        history_text = ""
        history = state.get("conversation_history", [])
        if history:
            history_text = "\n\n--- Conversation History ---\n"
            for msg in history[-10:]:
                history_text += f"{msg['role']}: {msg['content']}\n"
            history_text += "--- End History ---\n"

        # Inter-agent collaboration context
        inter_agent = state.get("metadata", {}).get("inter_agent_context", "")
        inter_agent_text = ""
        if inter_agent:
            inter_agent_text = f"\n\n--- Cross-Agent Intelligence ---\n{inter_agent}\n--- End Cross-Agent Intelligence ---\n"

        # Learning Genome: personalise the response to the student's cognitive profile
        genome_summary = state.get("metadata", {}).get("genome_summary", "")
        genome_text = ""
        if genome_summary:
            genome_text = (
                f"\n\n--- Learning Genome (adapt your response to this student) ---\n"
                f"{genome_summary}\n--- End Learning Genome ---\n"
            )

        return (
            f"{self.system_prompt}\n{context_text}\n{GROUNDING_INSTRUCTION}"
            f"\n{inter_agent_text}\n{genome_text}\n{history_text}\nStudent: {user_message}"
        )

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        provider = get_llm_provider()
        full_prompt = self._build_full_prompt(state, context)

        try:
            response = provider.generate(full_prompt, temperature=0.7, max_tokens=4096)
            note = grounding_note(context, response, settings.RAG_MIN_GROUNDING_SCORE)
            return response + note if note else response
        except Exception as e:
            logger.error("agent_reason_failed", agent=self.name, provider=provider.name, error=str(e))
            return describe_llm_error(e)

    async def _reason_stream(
        self, state: AgentState, context: list[dict]
    ) -> AsyncGenerator[str, None]:
        provider = get_llm_provider()
        full_prompt = self._build_full_prompt(state, context)

        full_response = ""
        try:
            async for token in provider.generate_stream(full_prompt, temperature=0.7, max_tokens=4096):
                full_response += token
                yield token
            note = grounding_note(context, full_response, settings.RAG_MIN_GROUNDING_SCORE)
            if note:
                yield note
        except Exception as e:
            logger.error("agent_stream_failed", agent=self.name, provider=provider.name, error=str(e))
            yield describe_llm_error(e)

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        return []
