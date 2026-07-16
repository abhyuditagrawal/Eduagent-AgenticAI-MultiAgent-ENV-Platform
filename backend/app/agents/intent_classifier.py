import structlog
import google.generativeai as genai

from app.agents.state import AgentState
from app.services.llm import get_gemini_model

logger = structlog.get_logger()

CLASSIFICATION_PROMPT = """Classify the user's intent into exactly one of these categories:
- conceptual_doubt: Asking about a concept, theory, definition, or "how does X work"
- exam_prep: Asking about exam preparation, past papers, important topics, practice questions
- weak_points: Asking about their weak areas, what to revise, what they're struggling with
- teach_me: Offering to explain/teach a concept (Feynman technique / protege mode)
- viva: Requesting a viva/oral exam simulation
- critique: Submitting an essay, assignment, or long text for feedback
- general: Greetings, meta questions, off-topic

User message: "{message}"

Respond with ONLY the category name, nothing else."""

VALID_INTENTS = {
    "conceptual_doubt",
    "exam_prep",
    "weak_points",
    "teach_me",
    "viva",
    "critique",
    "general",
}


def classify_intent(state: AgentState) -> AgentState:
    messages = state.get("messages", [])
    if not messages:
        state["intent"] = "general"
        return state

    last_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

    model = get_gemini_model()
    prompt = CLASSIFICATION_PROMPT.format(message=last_message)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=20,
            ),
        )
        intent = response.text.strip().lower().replace(" ", "_")

        if intent not in VALID_INTENTS:
            logger.warning("invalid_intent_classified", raw=intent)
            intent = "general"

        state["intent"] = intent
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["intent"] = intent

        logger.info("intent_classified", intent=intent, message=last_message[:80])

    except Exception as e:
        logger.error("intent_classification_failed", error=str(e))
        state["intent"] = "general"
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["intent"] = "general"
        state["metadata"]["intent_error"] = str(e)

    return state
