import json
import uuid
from typing import AsyncGenerator

import structlog

from app.agents.state import AgentState
from app.agents.intent_classifier import classify_intent
from app.agents.concept_qa import ConceptQAAgent
from app.agents.exam_predictor import ExamPredictorAgent
from app.agents.base import BaseAgent

logger = structlog.get_logger()

# Agent instances (reuse)
_agents: dict[str, BaseAgent] = {}


def _get_agents() -> dict[str, BaseAgent]:
    global _agents
    if not _agents:
        from app.agents.weak_point_tracker import WeakPointTrackerAgent
        from app.agents.protege import ProtegeAgent
        from app.agents.viva import VivaAgent
        from app.agents.critique import CritiqueAgent

        _agents["concept_qa"] = ConceptQAAgent()
        _agents["exam_predictor"] = ExamPredictorAgent()
        _agents["weak_point_tracker"] = WeakPointTrackerAgent()
        _agents["protege"] = ProtegeAgent()
        _agents["viva"] = VivaAgent()
        _agents["critique"] = CritiqueAgent()

        fallback = BaseAgent()
        fallback.name = "general"
        fallback.system_prompt = (
            "You are EduAgent, a friendly AI educational assistant. "
            "Help the student with their question. If it's about a specific subject, "
            "use the provided context. Be helpful, clear, and encouraging."
        )
        _agents["general"] = fallback
    return _agents


INTENT_TO_AGENT = {
    "conceptual_doubt": "concept_qa",
    "exam_prep": "exam_predictor",
    "weak_points": "weak_point_tracker",
    "teach_me": "protege",
    "viva": "viva",
    "critique": "critique",
    "general": "general",
}


async def stream_agent_response(
    initial_state: AgentState,
) -> AsyncGenerator[tuple[str, dict], None]:
    state = initial_state.copy()

    # 1. Load state
    state["metadata"] = state.get("metadata", {})
    state["rag_context"] = state.get("rag_context", [])
    state["concept_ids_touched"] = state.get("concept_ids_touched", [])
    state["concept_updates"] = state.get("concept_updates", [])

    # 2. Check for active mode (multi-turn protege/viva)
    active_mode = state.get("metadata", {}).get("active_mode")
    if active_mode and not state.get("intent"):
        state["intent"] = active_mode
        state["metadata"]["intent"] = active_mode

    # 3. Classify intent (unless overridden or active mode)
    if not state.get("intent"):
        state = classify_intent(state)

    intent = state.get("intent", "general")
    agent_name = INTENT_TO_AGENT.get(intent, "general")

    # 3. Get the agent
    agents = _get_agents()
    agent = agents.get(agent_name, agents["general"])

    # 4. Stream the agent
    try:
        async for event_type, event_data in agent.run_streaming(state):
            yield (event_type, event_data)
    except Exception as e:
        logger.error("streaming_failed", error=str(e))
        yield ("error", {"message": str(e)})
        return

    # 5. Yield done
    yield (
        "done",
        {
            "conversation_id": state.get("_conversation_id", ""),
            "message_id": state.get("_message_id", ""),
            "agent_type": agent.name,
            "intent": intent,
        },
    )
