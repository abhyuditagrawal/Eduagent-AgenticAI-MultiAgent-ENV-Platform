import structlog
import google.generativeai as genai

from app.agents.base import BaseAgent
from app.agents.state import AgentState
from app.rag.retriever import retrieve
from app.services.llm import get_gemini_model

logger = structlog.get_logger()

EXAM_PREDICTOR_SYSTEM_PROMPT = """You are an exam preparation strategist for {subject_name}.

Your capabilities:
1. TOPIC PREDICTION: Analyse the syllabus structure and past paper patterns to predict likely exam topics.
2. PRACTICE QUESTIONS: Generate exam-style questions at the appropriate difficulty level.
3. STUDY PLAN: Suggest a prioritised study plan based on topic importance and the student's weak areas.
4. PAST PAPER ANALYSIS: When given past paper content, identify recurring question patterns.

Student's concept mastery:
{concept_confidences}

Weak areas (concepts below 40% confidence):
{weak_concepts}

Course material context:
{rag_context}

When generating practice questions:
- Include a mix of short-answer, long-answer, and application-based questions
- Tag each question with the concept(s) it tests
- Provide model answers when asked

When predicting important topics:
- Rank topics by: (a) syllabus weight, (b) frequency in past papers if available, (c) foundational importance
- Highlight topics the student is weak in that are also high-importance"""


class ExamPredictorAgent(BaseAgent):
    name = "exam_predictor"

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        if not subject_code:
            return []

        messages = state.get("messages", [])
        if not messages:
            return []

        query = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")
        # Augment query with exam-related terms for better retrieval
        augmented_query = f"{query} exam important topics question paper syllabus"
        return retrieve(augmented_query, subject_code, top_k=5)

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        subject_name = state.get("subject_name", "the subject")
        student_state = state.get("student_state", {})

        # Build mastery summary
        all_concepts = []
        weak_concepts = []
        for cid, cdata in student_state.items():
            all_concepts.append(
                f"- {cdata['concept_name']}: {cdata['confidence']:.0%}"
            )
            if cdata["confidence"] < 0.4:
                weak_concepts.append(
                    f"- {cdata['concept_name']} ({cdata['confidence']:.0%})"
                )

        conf_text = "\n".join(all_concepts) if all_concepts else "No concept data available yet."
        weak_text = "\n".join(weak_concepts) if weak_concepts else "None — great job!"

        context_text = ""
        if context:
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"

        system_prompt = EXAM_PREDICTOR_SYSTEM_PROMPT.format(
            subject_name=subject_name,
            concept_confidences=conf_text,
            weak_concepts=weak_text,
            rag_context=context_text or "No context available.",
        )

        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        history_text = ""
        history = state.get("conversation_history", [])
        if history:
            history_text = "\n\n--- Conversation History ---\n"
            for msg in history[-10:]:
                history_text += f"{msg['role']}: {msg['content']}\n"
            history_text += "--- End History ---\n"

        full_prompt = f"{system_prompt}\n{history_text}\nStudent: {user_message}"

        model = get_gemini_model()
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7, max_output_tokens=2048
                ),
            )
            return response.text
        except Exception as e:
            logger.error("exam_predictor_reason_failed", error=str(e))
            return "I apologize, but I encountered an error while generating exam predictions. Please try again."

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        # If the student is answering practice questions, assess them
        # For now, no auto-assessment — will be enhanced in future phases
        return []
