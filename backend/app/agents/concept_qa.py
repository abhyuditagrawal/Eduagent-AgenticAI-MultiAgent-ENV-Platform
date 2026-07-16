import json
import structlog
import google.generativeai as genai

from app.agents.base import BaseAgent
from app.agents.state import AgentState
from app.rag.retriever import retrieve
from app.services.llm import get_gemini_model

logger = structlog.get_logger()

CONCEPT_QA_SYSTEM_PROMPT = """You are an expert tutor for {subject_name}. Your role is to explain concepts clearly and thoroughly.

RULES:
1. Before explaining a concept, check if the student has gaps in prerequisites.
   If prerequisite gaps are found, briefly explain the prerequisite first, then the main concept.
2. Use the provided course material context to ground your explanations.
3. Use analogies and examples to make concepts accessible.
4. After explaining, ask a quick comprehension check question.
5. Adapt your language complexity based on the student's confidence level:
   - Low confidence (< 0.3): Use simple language, more analogies
   - Medium confidence (0.3-0.7): Standard academic language
   - High confidence (> 0.7): Concise, can use technical jargon

Student's current confidence in related concepts:
{concept_confidences}

Prerequisite gaps found:
{prerequisite_gaps}

Course material context:
{rag_context}"""

CONCEPT_MATCH_PROMPT = """Given the following user question and list of course concepts, identify which concepts (by name) are being asked about. Return ONLY a JSON array of concept names.

User question: "{question}"

Available concepts:
{concept_list}

Return a JSON array of matching concept names, e.g. ["Polymorphism", "Inheritance"]. If no concepts match, return [].
"""


class ConceptQAAgent(BaseAgent):
    name = "concept_qa"

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        if not subject_code:
            return []

        messages = state.get("messages", [])
        if not messages:
            return []

        query = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")
        chunks = retrieve(query, subject_code, top_k=5)

        # Identify which concepts are being asked about
        student_state = state.get("student_state", {})
        concept_names = [v["concept_name"] for v in student_state.values()]

        if concept_names:
            try:
                model = get_gemini_model()
                response = model.generate_content(
                    CONCEPT_MATCH_PROMPT.format(
                        question=query,
                        concept_list=", ".join(concept_names),
                    ),
                    generation_config=genai.GenerationConfig(
                        temperature=0.0, max_output_tokens=200
                    ),
                )
                raw = response.text.strip()
                if raw.startswith("["):
                    matched = json.loads(raw)
                    touched = []
                    for name in matched:
                        for cid, cdata in student_state.items():
                            if cdata["concept_name"].lower() == name.lower():
                                touched.append(cid)
                    state["concept_ids_touched"] = touched
            except Exception as e:
                logger.warning("concept_match_failed", error=str(e))

        return chunks

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        subject_name = state.get("subject_name", "the subject")
        student_state = state.get("student_state", {})
        touched = state.get("concept_ids_touched", [])

        # Build confidence summary for touched concepts
        confidences = {}
        for cid in touched:
            if cid in student_state:
                c = student_state[cid]
                confidences[c["concept_name"]] = c["confidence"]

        # Find prerequisite gaps (from metadata if populated by orchestrator)
        prereq_gaps = state.get("metadata", {}).get("prerequisite_gaps", [])
        gaps_text = "None" if not prereq_gaps else "\n".join(
            f"- {g['concept_name']} (confidence: {g['confidence']:.0%})" for g in prereq_gaps
        )

        conf_text = "None assessed yet" if not confidences else "\n".join(
            f"- {name}: {conf:.0%}" for name, conf in confidences.items()
        )

        context_text = ""
        if context:
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"

        system_prompt = CONCEPT_QA_SYSTEM_PROMPT.format(
            subject_name=subject_name,
            concept_confidences=conf_text,
            prerequisite_gaps=gaps_text,
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
            logger.error("concept_qa_reason_failed", error=str(e))
            return "I apologize, but I encountered an error. Please try again."

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        # Check if the user's message is an answer to a previous comprehension check
        messages = state.get("messages", [])
        history = state.get("conversation_history", [])

        if len(history) >= 2:
            prev_assistant = None
            for msg in reversed(history[:-1]):
                if msg["role"] == "assistant":
                    prev_assistant = msg["content"]
                    break

            if prev_assistant and "?" in prev_assistant:
                user_msg = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")
                touched = state.get("concept_ids_touched", [])

                if touched and len(user_msg) > 10:
                    quality = await self._llm_assess_answer(
                        prev_assistant, user_msg, state
                    )
                    return [
                        {"concept_id": cid, "quality": quality}
                        for cid in touched[:3]
                    ]

        return []

    async def _llm_assess_answer(
        self, question_context: str, student_answer: str, state: AgentState
    ) -> int:
        """Use the LLM to evaluate student answer quality on a 1-5 scale."""
        rag_context = state.get("rag_context", [])
        ground_truth = ""
        if rag_context:
            ground_truth = "\n".join(
                c.get("text", "")[:300] for c in rag_context[:3]
            )

        assess_prompt = (
            "You are an educational assessment engine. Evaluate the student's answer "
            "to a comprehension check question.\n\n"
            f"Question/Context from tutor:\n{question_context[-500:]}\n\n"
            f"Student's answer:\n{student_answer}\n\n"
        )
        if ground_truth:
            assess_prompt += (
                f"Ground truth from course material:\n{ground_truth}\n\n"
            )
        assess_prompt += (
            "Rate the student's understanding on a scale of 1-5:\n"
            "1 = Complete misconception or irrelevant answer\n"
            "2 = Partially wrong with significant gaps\n"
            "3 = Roughly correct but superficial or incomplete\n"
            "4 = Correct with good understanding\n"
            "5 = Excellent, thorough and precise answer\n\n"
            "Respond with ONLY a single integer (1-5), nothing else."
        )

        try:
            model = get_gemini_model()
            resp = model.generate_content(
                assess_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.0, max_output_tokens=5
                ),
            )
            score_text = resp.text.strip()
            score = int(score_text[0]) if score_text and score_text[0].isdigit() else 3
            return max(1, min(5, score))
        except Exception as e:
            logger.warning("llm_assessment_failed", error=str(e))
            # Fallback to improved heuristic
            word_count = len(student_answer.split())
            if word_count < 5:
                return 2
            elif word_count < 20:
                return 3
            else:
                return 4
