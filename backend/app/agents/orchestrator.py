import structlog
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.intent_classifier import classify_intent
from app.agents.concept_qa import ConceptQAAgent
from app.agents.exam_predictor import ExamPredictorAgent
from app.agents.weak_point_tracker import WeakPointTrackerAgent
from app.agents.protege import ProtegeAgent
from app.agents.viva import VivaAgent
from app.agents.critique import CritiqueAgent
from app.agents.security_tools_agent import SecurityToolsAgent
from app.agents.base import BaseAgent

logger = structlog.get_logger()

# Agent instances
concept_qa_agent = ConceptQAAgent()
exam_predictor_agent = ExamPredictorAgent()
weak_point_agent = WeakPointTrackerAgent()
protege_agent = ProtegeAgent()
viva_agent = VivaAgent()
critique_agent = CritiqueAgent()
security_tools_agent = SecurityToolsAgent()

fallback_agent = BaseAgent()
fallback_agent.name = "general"
fallback_agent.system_prompt = (
    "You are EduAgent, a friendly AI educational assistant. "
    "Help the student with their question. If it's about a specific subject, "
    "use the provided context. Be helpful, clear, and encouraging. "
    "If you can't answer, suggest which mode might help (e.g., 'Try asking me about exam preparation!')."
)


# --- Graph Nodes ---

def load_state_node(state: AgentState) -> AgentState:
    state["metadata"] = state.get("metadata", {})
    state["rag_context"] = state.get("rag_context", [])
    state["concept_ids_touched"] = state.get("concept_ids_touched", [])
    state["concept_updates"] = state.get("concept_updates", [])
    state["metadata"]["step"] = "load_state"
    logger.info("orchestrator_load_state", student_id=state.get("student_id"))
    return state


def classify_node(state: AgentState) -> AgentState:
    # If conversation has an active mode, skip classification and route to that agent
    active_mode = state.get("metadata", {}).get("active_mode")
    if active_mode:
        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "") if messages else ""
        end_keywords = ["end teaching", "stop teaching", "end viva", "stop viva", "finish viva", "exit mode", "quit"]
        if any(kw in user_message.lower() for kw in end_keywords):
            state["intent"] = active_mode
            state["metadata"]["ending_mode"] = True
        else:
            state["intent"] = active_mode
            state["metadata"]["intent"] = active_mode
            logger.info("orchestrator_active_mode", mode=active_mode)
            return state

    state = classify_intent(state)
    logger.info("orchestrator_classify", intent=state.get("intent"))
    return state


def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "general")
    routing = {
        "conceptual_doubt": "agent_qa",
        "exam_prep": "agent_exam",
        "weak_points": "agent_weak_point",
        "teach_me": "agent_protege",
        "viva": "agent_viva",
        "critique": "agent_critique",
        "security_tool": "agent_security_tool",
        "general": "agent_fallback",
    }
    route = routing.get(intent, "agent_fallback")
    logger.info("orchestrator_route", intent=intent, route=route)
    return route


async def agent_qa_node(state: AgentState) -> AgentState:
    return await concept_qa_agent.run(state)


async def agent_exam_node(state: AgentState) -> AgentState:
    return await exam_predictor_agent.run(state)


async def agent_weak_point_node(state: AgentState) -> AgentState:
    return await weak_point_agent.run(state)


async def agent_protege_node(state: AgentState) -> AgentState:
    return await protege_agent.run(state)


async def agent_viva_node(state: AgentState) -> AgentState:
    return await viva_agent.run(state)


async def agent_critique_node(state: AgentState) -> AgentState:
    return await critique_agent.run(state)


async def agent_security_tool_node(state: AgentState) -> AgentState:
    return await security_tools_agent.run(state)


async def agent_fallback_node(state: AgentState) -> AgentState:
    return await fallback_agent.run(state)


def commit_state_node(state: AgentState) -> AgentState:
    state["metadata"]["step"] = "commit_state"
    state["metadata"]["concept_updates"] = state.get("concept_updates", [])
    state["metadata"]["concepts_touched"] = state.get("concept_ids_touched", [])
    logger.info(
        "orchestrator_commit",
        updates=len(state.get("concept_updates", [])),
    )
    return state


def format_response_node(state: AgentState) -> AgentState:
    state["metadata"]["step"] = "format_response"
    state["metadata"]["agent_type"] = state.get("active_agent", "unknown")
    return state


# --- Build Graph ---

def build_orchestrator_graph():
    graph = StateGraph(AgentState)

    graph.add_node("load_state", load_state_node)
    graph.add_node("classify", classify_node)
    graph.add_node("agent_qa", agent_qa_node)
    graph.add_node("agent_exam", agent_exam_node)
    graph.add_node("agent_weak_point", agent_weak_point_node)
    graph.add_node("agent_protege", agent_protege_node)
    graph.add_node("agent_viva", agent_viva_node)
    graph.add_node("agent_critique", agent_critique_node)
    graph.add_node("agent_security_tool", agent_security_tool_node)
    graph.add_node("agent_fallback", agent_fallback_node)
    graph.add_node("commit_state", commit_state_node)
    graph.add_node("format_response", format_response_node)

    graph.set_entry_point("load_state")
    graph.add_edge("load_state", "classify")

    graph.add_conditional_edges(
        "classify",
        route_intent,
        {
            "agent_qa": "agent_qa",
            "agent_exam": "agent_exam",
            "agent_weak_point": "agent_weak_point",
            "agent_protege": "agent_protege",
            "agent_viva": "agent_viva",
            "agent_critique": "agent_critique",
            "agent_security_tool": "agent_security_tool",
            "agent_fallback": "agent_fallback",
        },
    )

    graph.add_edge("agent_qa", "commit_state")
    graph.add_edge("agent_exam", "commit_state")
    graph.add_edge("agent_weak_point", "commit_state")
    graph.add_edge("agent_protege", "commit_state")
    graph.add_edge("agent_viva", "commit_state")
    graph.add_edge("agent_critique", "commit_state")
    graph.add_edge("agent_security_tool", "commit_state")
    graph.add_edge("agent_fallback", "commit_state")
    graph.add_edge("commit_state", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()


# Singleton compiled graph
_orchestrator = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = build_orchestrator_graph()
    return _orchestrator
