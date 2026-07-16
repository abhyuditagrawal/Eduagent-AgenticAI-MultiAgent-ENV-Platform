from typing import AsyncGenerator

import structlog
import google.generativeai as genai

from app.agents.state import AgentState
from app.services.llm import get_gemini_model
from app.rag.retriever import retrieve

logger = structlog.get_logger()


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

        return f"{self.system_prompt}\n{context_text}\n{history_text}\nStudent: {user_message}"

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        model = get_gemini_model()
        full_prompt = self._build_full_prompt(state, context)

        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            return response.text
        except Exception as e:
            logger.error("agent_reason_failed", agent=self.name, error=str(e))
            return "I apologize, but I encountered an error while processing your request. Please try again."

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
                    max_output_tokens=2048,
                ),
                stream=True,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error("agent_stream_failed", agent=self.name, error=str(e))
            yield "I apologize, but I encountered an error while processing your request."

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        return []
