import json
import time
import uuid
from typing import AsyncGenerator

import structlog

from app.agents.state import AgentState
from app.agents.intent_classifier import classify_intent
from app.agents.concept_qa import ConceptQAAgent
from app.agents.exam_predictor import ExamPredictorAgent
from app.agents.base import BaseAgent
from app.services.cache import cache_get, cache_set

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


def _enrich_with_inter_agent_context(state: AgentState, intent: str) -> AgentState:
    """Inter-agent collaboration: agents consult each other's data before responding.

    - Concept QA checks weak points to address prerequisites first
    - Exam Predictor skips mastered topics
    - Protege considers weak areas for probing
    """
    student_state = state.get("student_state", {})
    if not student_state:
        return state

    metadata = state.get("metadata", {})

    # Find weak concepts (confidence < 0.4)
    weak_concepts = [
        {"id": cid, "name": cdata.get("concept_name", ""), "confidence": cdata.get("confidence", 0)}
        for cid, cdata in student_state.items()
        if cdata.get("confidence", 0) < 0.4
    ]

    # Find mastered concepts (confidence >= 0.8)
    mastered_concepts = [
        {"id": cid, "name": cdata.get("concept_name", "")}
        for cid, cdata in student_state.items()
        if cdata.get("confidence", 0) >= 0.8
    ]

    # Find overdue concepts
    overdue_concepts = [
        {"id": cid, "name": cdata.get("concept_name", "")}
        for cid, cdata in student_state.items()
        if cdata.get("is_overdue", False)
    ]

    if intent == "conceptual_doubt" and weak_concepts:
        # Concept QA: inject prerequisite gap awareness
        weak_names = [w["name"] for w in weak_concepts[:5]]
        metadata["inter_agent_context"] = (
            f"PREREQUISITE ALERT: The student has weak spots in: {', '.join(weak_names)}. "
            f"If the current question depends on any of these, address the gap first."
        )

    elif intent == "exam_prep" and mastered_concepts:
        # Exam Predictor: skip mastered topics
        mastered_names = [m["name"] for m in mastered_concepts[:10]]
        metadata["inter_agent_context"] = (
            f"The student has already mastered: {', '.join(mastered_names)}. "
            f"Focus practice questions on topics they haven't mastered yet."
        )

    elif intent in ("teach_me", "viva") and weak_concepts:
        # Protege/Viva: probe weak areas
        weak_names = [w["name"] for w in weak_concepts[:5]]
        metadata["inter_agent_context"] = (
            f"WEAK AREA PROBE: The student struggles with: {', '.join(weak_names)}. "
            f"If the teaching topic relates to these, ask probing questions about them."
        )

    elif intent == "weak_points" and overdue_concepts:
        overdue_names = [o["name"] for o in overdue_concepts[:5]]
        metadata["inter_agent_context"] = (
            f"OVERDUE REVIEWS: {', '.join(overdue_names)} are overdue for review. "
            f"Prioritize these in recommendations."
        )

    state["metadata"] = metadata
    return state


async def stream_agent_response(
    initial_state: AgentState,
) -> AsyncGenerator[tuple[str, dict], None]:
    start_time = time.time()
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

    # 4. Inter-agent collaboration: enrich state with cross-agent context
    state = _enrich_with_inter_agent_context(state, intent)

    # 5. Get the agent
    agents = _get_agents()
    agent = agents.get(agent_name, agents["general"])

    # 6. Stream the agent
    response_time_ms = 0
    try:
        async for event_type, event_data in agent.run_streaming(state):
            yield (event_type, event_data)
    except Exception as e:
        logger.error("streaming_failed", error=str(e))
        yield ("error", {"message": str(e)})
        return

    response_time_ms = int((time.time() - start_time) * 1000)

    # 7. Yield done with performance metrics
    yield (
        "done",
        {
            "conversation_id": state.get("_conversation_id", ""),
            "message_id": state.get("_message_id", ""),
            "agent_type": agent.name,
            "intent": intent,
            "response_time_ms": response_time_ms,
            "rag_chunks_used": len(state.get("rag_context", [])),
        },
    )
