import re

import structlog

from app.agents.base import BaseAgent
from app.agents.state import AgentState
from app.rag.retriever import retrieve

logger = structlog.get_logger()

VIVA_SYSTEM_PROMPT = """You are an academic examiner conducting a viva voce (oral examination) for {subject_name}.

BEHAVIOUR:
1. Start by greeting the student and announcing the topic area
2. Ask questions in increasing difficulty order:
   - Start with a foundational definition/concept question (Tier 1)
   - Progress to application questions (Tier 2)
   - End with analysis/synthesis questions (Tier 3)
3. After each student answer:
   - Internally score it (do not reveal score yet)
   - Either: (a) probe deeper on the same topic, (b) move to next question, or (c) redirect if answer was off-track
4. Probing techniques:
   - "Can you elaborate on that?"
   - "How would that apply in [specific scenario]?"
   - "What's the difference between X and Y?"
   - "That's interesting — but what about [edge case]?"
5. After {max_questions} questions, conclude the viva with a structured evaluation

DIFFICULTY ADAPTATION:
- Check student's confidence levels for each concept
- Skip easy questions on concepts with confidence > 0.8
- Spend more time on concepts with confidence 0.3-0.6
- Gently introduce concepts with confidence < 0.3

Available concepts for this subject (with student confidence):
{concept_confidences}

Concepts to focus on (based on priority):
{priority_concepts}

Course material for reference:
{rag_context}

Current viva state:
- Question {current_question} of {max_questions}
- Difficulty level: {difficulty_level}
- Questions asked so far: {questions_summary}

{evaluation_instruction}"""

VIVA_EVALUATION_INSTRUCTION = """
IMPORTANT: You have asked all your questions. Now provide a complete structured evaluation:

## Viva Evaluation

**Subject**: {subject_name}
**Duration**: {num_questions} questions
**Overall Grade**: [A/B/C/D/F]

### Question-by-Question Breakdown
| # | Topic | Score | Notes |
|---|-------|-------|-------|
[Fill in for each question asked]

### Strengths
- [What the student demonstrated well]

### Areas for Improvement
- [Where the student struggled]

### Recommended Study Areas
- [Specific concepts to review]
"""


class VivaAgent(BaseAgent):
    name = "viva"

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        if not subject_code:
            return []

        student_state = state.get("student_state", {})
        agent_ctx = state.get("metadata", {}).get("agent_context", {})

        # Focus RAG on priority concepts
        priority_concepts = agent_ctx.get("priority_concepts", [])
        if priority_concepts:
            query = "Exam topics: " + ", ".join(priority_concepts[:5])
        else:
            # Use weak concepts
            weak = [
                v["concept_name"] for v in student_state.values()
                if v.get("confidence", 0) < 0.6
            ][:5]
            if weak:
                query = "Key concepts: " + ", ".join(weak)
            else:
                messages = state.get("messages", [])
                query = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "") if messages else "viva exam"

        return retrieve(query, subject_code, top_k=5)

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        from app.services.llm import get_gemini_model
        import google.generativeai as genai

        subject_name = state.get("subject_name", "the subject")
        student_state = state.get("student_state", {})
        agent_ctx = state.get("metadata", {}).get("agent_context", {})

        current_question = agent_ctx.get("current_question_index", 0)
        max_questions = agent_ctx.get("max_questions", 8)
        difficulty_level = agent_ctx.get("difficulty_level", 1)
        viva_questions = agent_ctx.get("viva_questions", [])
        priority_concepts = agent_ctx.get("priority_concepts", [])

        # Build confidence table
        conf_rows = []
        for cdata in sorted(student_state.values(), key=lambda x: x.get("confidence", 0)):
            conf = cdata.get("confidence", 0)
            name = cdata.get("concept_name", "Unknown")
            conf_rows.append(f"- {name}: {conf:.0%}")
        conf_text = "\n".join(conf_rows[:20]) if conf_rows else "No concept data available."

        priority_text = ", ".join(priority_concepts[:8]) if priority_concepts else "Focus on weakest areas."

        # Questions summary
        q_summary = "None yet."
        if viva_questions:
            q_lines = []
            for i, q in enumerate(viva_questions, 1):
                q_lines.append(f"Q{i}: {q.get('question', 'N/A')[:60]} — Answer quality: {q.get('score', '?')}/10")
            q_summary = "\n".join(q_lines)

        # Context text
        context_text = ""
        if context:
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"

        # Check if should evaluate
        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        should_evaluate = (
            current_question >= max_questions
            or any(kw in user_message.lower() for kw in ["end viva", "stop viva", "finish viva"])
        )

        eval_instruction = ""
        if should_evaluate:
            eval_instruction = VIVA_EVALUATION_INSTRUCTION.format(
                subject_name=subject_name,
                num_questions=current_question,
            )

        difficulty_names = {1: "Easy (Tier 1 — Definitions)", 2: "Medium (Tier 2 — Application)", 3: "Hard (Tier 3 — Analysis)"}

        system_prompt = VIVA_SYSTEM_PROMPT.format(
            subject_name=subject_name,
            concept_confidences=conf_text,
            priority_concepts=priority_text,
            rag_context=context_text or "No course material available.",
            current_question=current_question + 1,
            max_questions=max_questions,
            difficulty_level=difficulty_names.get(difficulty_level, "Medium"),
            questions_summary=q_summary,
            evaluation_instruction=eval_instruction,
        )

        history_text = ""
        history = state.get("conversation_history", [])
        if history:
            history_text = "\n\n--- Conversation History ---\n"
            for msg in history[-16:]:
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
            logger.error("viva_reason_failed", error=str(e))
            return "Let me rephrase that question. Could you tell me about the key principles we've been discussing?"

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        agent_ctx = state.get("metadata", {}).get("agent_context", {})
        current_question = agent_ctx.get("current_question_index", 0)
        max_questions = agent_ctx.get("max_questions", 8)

        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        should_evaluate = (
            current_question >= max_questions
            or any(kw in user_message.lower() for kw in ["end viva", "stop viva", "finish viva"])
        )

        if not should_evaluate:
            return []

        # Extract scores from evaluation table
        updates = []
        student_state = state.get("student_state", {})

        # Try to extract overall grade
        grade_match = re.search(r"\*\*Overall Grade\*\*:\s*([A-F])", response)
        grade_to_quality = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}

        if grade_match:
            quality = grade_to_quality.get(grade_match.group(1), 3)
        else:
            quality = 3

        # Apply quality to all concepts mentioned in priority list
        priority_concepts = agent_ctx.get("priority_concepts", [])
        for cid, cdata in student_state.items():
            cname = cdata.get("concept_name", "")
            if cname in priority_concepts:
                updates.append({"concept_id": cid, "quality": quality})

        # Limit to prevent over-updating
        return updates[:10]
