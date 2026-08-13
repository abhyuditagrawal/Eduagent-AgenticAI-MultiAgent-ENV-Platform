import re
from typing import AsyncGenerator

import structlog
import google.generativeai as genai

from app.agents.state import AgentState
from app.services.llm import get_gemini_model
from app.rag.retriever import retrieve

logger = structlog.get_logger()


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

        return f"{self.system_prompt}\n{context_text}\n{inter_agent_text}\n{genome_text}\n{history_text}\nStudent: {user_message}"

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        model = get_gemini_model()
        full_prompt = self._build_full_prompt(state, context)

        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=4096,
                ),
            )
            return response.text
        except Exception as e:
            logger.error("agent_reason_failed", agent=self.name, error=str(e))
            return describe_llm_error(e)

    async def _reason_stream(
        self, state: AgentState, context: list[dict]
    ) -> AsyncGenerator[str, None]:
        model = get_gemini_model()
        full_prompt = self._build_full_prompt(state, context)

        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=4096,
                ),
                stream=True,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error("agent_stream_failed", agent=self.name, error=str(e))
            yield describe_llm_error(e)

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        return []
