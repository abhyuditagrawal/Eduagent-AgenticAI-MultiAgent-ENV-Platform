from datetime import datetime, timezone

import structlog

from app.agents.base import BaseAgent
from app.agents.state import AgentState
from app.rag.retriever import retrieve

logger = structlog.get_logger()

WEAK_POINT_SYSTEM_PROMPT = """You are a learning diagnostician for {subject_name}. Your role is to help students identify and address their weak areas.

CAPABILITIES:
1. WEAK POINT ANALYSIS: Review the student's concept mastery data and identify patterns:
   - Concepts with low confidence scores
   - Concepts that are prerequisites for many others (high-impact gaps)
   - Concepts where confidence is decaying (not reviewed recently)
   - Concepts with many attempts but low success rate (persistent confusion)

2. TARGETED REVIEW: Generate focused review material for weak concepts:
   - Concise concept summaries
   - Key points to remember
   - Common misconceptions to avoid
   - Quick self-test questions

3. STUDY SCHEDULING: Suggest which concepts to review next based on:
   - Spaced repetition schedule (concepts overdue for review)
   - Prerequisite ordering (review foundations before advanced topics)
   - Exam proximity (if mentioned by student)

4. PROGRESS TRACKING: When the student asks about their progress:
   - Summarise mastery levels across the subject
   - Highlight improvements since last check
   - Identify persistent weak areas

Student's full concept mastery data:
{concept_mastery_table}

Concepts overdue for review (next_review_at < now):
{overdue_concepts}

Prerequisite gaps (concepts with unmastered prerequisites):
{prerequisite_gaps}

Course material context:
{rag_context}

IMPORTANT: Always be encouraging. Frame weaknesses as "opportunities for growth" not failures.
When listing weak areas, also acknowledge concepts the student has mastered well."""


class WeakPointTrackerAgent(BaseAgent):
    name = "weak_point_tracker"

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        student_state = state.get("student_state", {})

        # Identify weak concepts
        weak_concepts = [
            v for v in student_state.values() if v.get("confidence", 0) < 0.4
        ]

        # RAG search for weak concept names
        chunks = []
        if subject_code and weak_concepts:
            weak_names = [c["concept_name"] for c in weak_concepts[:5]]
            query = "Review: " + ", ".join(weak_names)
            chunks = retrieve(query, subject_code, top_k=5)
        elif subject_code:
            messages = state.get("messages", [])
            if messages:
                query = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")
                chunks = retrieve(query, subject_code, top_k=5)

        return chunks

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        from app.services.llm import get_gemini_model
        import google.generativeai as genai

        subject_name = state.get("subject_name", "the subject")
        student_state = state.get("student_state", {})

        # Build mastery table
        mastery_rows = []
        weak_rows = []
        overdue_rows = []
        now = datetime.now(timezone.utc)

        for cid, cdata in student_state.items():
            conf = cdata.get("confidence", 0)
            name = cdata.get("concept_name", "Unknown")
            attempts = cdata.get("attempts", 0)
            correct = cdata.get("correct_count", 0)
            chapter = cdata.get("chapter", "")

            level = "🟢 Mastered" if conf >= 0.8 else "🟡 Proficient" if conf >= 0.5 else "🟠 Developing" if conf >= 0.2 else "🔴 Not Started"
            mastery_rows.append(
                f"- {name} ({chapter}): {conf:.0%} — {level} ({attempts} attempts, {correct} correct)"
            )

            if conf < 0.4:
                weak_rows.append(f"- {name}: {conf:.0%}")

            next_review = cdata.get("next_review")
            if next_review:
                try:
                    review_dt = datetime.fromisoformat(next_review)
                    if review_dt.tzinfo is None:
                        review_dt = review_dt.replace(tzinfo=timezone.utc)
                    if review_dt < now:
                        days_overdue = (now - review_dt).days
                        overdue_rows.append(
                            f"- {name}: {days_overdue} days overdue"
                        )
                except (ValueError, TypeError):
                    pass

        mastery_text = "\n".join(mastery_rows) if mastery_rows else "No concept data available yet."
        overdue_text = "\n".join(overdue_rows) if overdue_rows else "None — all reviews are on schedule!"
        prereq_text = "See mastery data above for prerequisite relationships."

        context_text = ""
        if context:
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"

        system_prompt = WEAK_POINT_SYSTEM_PROMPT.format(
            subject_name=subject_name,
            concept_mastery_table=mastery_text,
            overdue_concepts=overdue_text,
            prerequisite_gaps=prereq_text,
            rag_context=context_text or "No additional context available.",
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
                    temperature=0.7, max_output_tokens=4096
                ),
            )
            return response.text
        except Exception as e:
            logger.error("weak_point_reason_failed", error=str(e))
            return "I apologize, but I encountered an error analyzing your progress. Please try again."

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        # This agent diagnoses; it never tests the student, so it has no evidence
        # to change mastery with. Record which weak concepts were surfaced so the
        # activity analytics show real coverage, but leave the scores untouched.
        student_state = state.get("student_state", {})
        state["concept_ids_touched"] = [
            cid
            for cid, v in student_state.items()
            if v.get("confidence", 0) < 0.4
        ][:5]
        return []
