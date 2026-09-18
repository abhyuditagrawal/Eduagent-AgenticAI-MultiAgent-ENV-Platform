import re

import structlog
import google.generativeai as genai

from app.agents.state import AgentState
from app.services.llm import get_gemini_model

logger = structlog.get_logger()

# Future Work item #1: "fine-tuning a smaller, faster model ... for intent
# classification to reduce latency from the current LLM-based approach."
# Training and serving a dedicated classifier is out of scope for this
# pass, but a big share of real traffic is unambiguous enough for a cheap
# rule-based fast path to skip the LLM round-trip entirely - viva/critique/
# teach-me requests are almost always phrased with one of a handful of verbs.
# Ambiguous phrasing still falls through to the LLM classifier below.
_FAST_PATH_RULES: list[tuple[str, re.Pattern]] = [
    ("viva", re.compile(r"\b(start|begin|do)\s+(a\s+)?(oral\s+)?viva\b|\bviva\s+(exam|practice|session)\b", re.I)),
    ("teach_me", re.compile(r"\b(let me teach|i(?:'ll| will) teach|teach you|explain (?:it|this) to you)\b", re.I)),
    ("critique", re.compile(r"\b(review|critique|grade|feedback on) (my|this|the) (essay|assignment|paper|submission)\b", re.I)),
    ("exam_prep", re.compile(r"\b(exam prep|important topics|practice questions|past papers?|exam pattern)\b", re.I)),
    ("weak_points", re.compile(r"\b(my weak (points|areas)|what.{0,10}(struggl|weak)|what should i revise)\b", re.I)),
    ("general", re.compile(r"^\s*(hi|hello|hey|thanks|thank you|ok|okay)\s*[.!]?\s*$", re.I)),
]


def _fast_path_intent(message: str) -> str | None:
    for intent, pattern in _FAST_PATH_RULES:
        if pattern.search(message):
            return intent
    return None

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

    fast_intent = _fast_path_intent(last_message)
    if fast_intent:
        state["intent"] = fast_intent
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["intent"] = fast_intent
        state["metadata"]["intent_source"] = "fast_path"
        logger.info("intent_classified_fast_path", intent=fast_intent, message=last_message[:80])
        return state

    model = get_gemini_model()
    prompt = CLASSIFICATION_PROMPT.format(message=last_message)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                # The answer is one word, but current models spend output tokens
                # reasoning first and return nothing at all if cut off mid-thought.
                max_output_tokens=256,
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
