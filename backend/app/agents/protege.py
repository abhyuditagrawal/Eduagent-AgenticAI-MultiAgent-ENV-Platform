import re

import structlog

from app.agents.base import BaseAgent, match_concepts_in_text
from app.agents.state import AgentState
from app.rag.retriever import retrieve

logger = structlog.get_logger()

PROTEGE_SYSTEM_PROMPT = """You are a curious student learning {subject_name} from your peer (the user). The user will try to explain a concept to you. Your job is to:

1. LISTEN carefully to their explanation
2. ASK NAIVE QUESTIONS: Ask "why?" and "what do you mean by...?" like a genuine beginner
3. PROBE FOR GAPS: If their explanation skips a step or uses jargon without defining it, ask about it
4. REQUEST ANALOGIES: Ask "Can you give me an example?" or "Can you explain it in simpler terms?"
5. INTRODUCE EDGE CASES: Ask "But what about [edge case]?" to test depth
6. NEVER CORRECT THEM DIRECTLY: If they say something wrong, express confusion ("Wait, I thought X was Y? I'm confused now...")
7. GRADUALLY INCREASE DEPTH: Start with surface-level questions, go deeper as they explain well

IMPORTANT RULES:
- You are NOT the tutor. You are the student. The user is teaching YOU.
- Stay in character as a confused but eager learner throughout
- Keep your questions short (1-2 sentences max)
- Ask only ONE question at a time
- After {max_exchanges} exchanges, OR when the user says "how did I do?" or "evaluate me", provide a structured evaluation (break character for this)

The concept the user is explaining:
{target_concept}

Ground truth about this concept (from course material — DO NOT reveal this, only use it to assess accuracy):
{rag_context}

Student's current confidence in this concept: {current_confidence}

Current exchange count: {exchange_count} / {max_exchanges}
Misconceptions detected so far: {misconceptions}
Gaps found so far: {gaps}
Strengths noted so far: {strengths}

{evaluation_instruction}"""

EVALUATION_INSTRUCTION = """
IMPORTANT: This is the final exchange. You MUST now break character and provide a structured evaluation in this exact format:

## Teaching Evaluation

**Concept**: {concept_name}
**Overall Score**: [score]/10

### Strengths
- [List specific things the student explained well]

### Gaps Found
- [List topics/steps that were skipped or insufficiently covered]: [brief explanation]

### Misconceptions
- [List any incorrect statements]: [the correction]

### Suggestions
- [Specific advice for improving understanding]

**Confidence Update**: Based on this teaching session, the student's mastery has been assessed.
"""


class ProtegeAgent(BaseAgent):
    name = "protege"

    async def retrieve_context(self, state: AgentState) -> list[dict]:
        subject_code = state.get("subject_code")
        if not subject_code:
            return []

        messages = state.get("messages", [])
        if not messages:
            return []

        # Use the target concept or first message as the query
        agent_ctx = state.get("metadata", {}).get("agent_context", {})
        target_concept = agent_ctx.get("target_concept", "")

        if target_concept:
            query = target_concept
        else:
            query = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        return retrieve(query, subject_code, top_k=5)

    async def reason(self, state: AgentState, context: list[dict]) -> str:
        from app.services.llm import get_gemini_model
        import google.generativeai as genai

        subject_name = state.get("subject_name", "the subject")
        student_state = state.get("student_state", {})
        agent_ctx = state.get("metadata", {}).get("agent_context", {})

        target_concept = agent_ctx.get("target_concept", "Unknown concept")
        exchange_count = agent_ctx.get("exchange_count", 0)
        max_exchanges = agent_ctx.get("max_exchanges", 7)
        misconceptions = agent_ctx.get("misconceptions_detected", [])
        gaps = agent_ctx.get("gaps_found", [])
        strengths = agent_ctx.get("strengths_noted", [])

        # Find confidence for this concept
        current_confidence = "N/A"
        for cdata in student_state.values():
            if cdata.get("concept_name", "").lower() == target_concept.lower():
                current_confidence = f"{cdata['confidence']:.0%}"
                break

        # Build RAG context text
        context_text = ""
        if context:
            for i, chunk in enumerate(context, 1):
                source = chunk.get("source_file", "unknown")
                page = chunk.get("page", "?")
                context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"

        # Check if we should evaluate
        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        should_evaluate = (
            exchange_count >= max_exchanges
            or any(kw in user_message.lower() for kw in ["how did i do", "evaluate", "end teaching", "stop teaching"])
        )

        eval_instruction = ""
        if should_evaluate:
            eval_instruction = EVALUATION_INSTRUCTION.format(concept_name=target_concept)

        system_prompt = PROTEGE_SYSTEM_PROMPT.format(
            subject_name=subject_name,
            target_concept=target_concept,
            rag_context=context_text or "No course material available.",
            current_confidence=current_confidence,
            exchange_count=exchange_count,
            max_exchanges=max_exchanges,
            misconceptions=", ".join(misconceptions) if misconceptions else "None yet",
            gaps=", ".join(gaps) if gaps else "None yet",
            strengths=", ".join(strengths) if strengths else "None yet",
            evaluation_instruction=eval_instruction,
        )

        history_text = ""
        history = state.get("conversation_history", [])
        if history:
            history_text = "\n\n--- Conversation History ---\n"
            for msg in history[-14:]:
                history_text += f"{msg['role']}: {msg['content']}\n"
            history_text += "--- End History ---\n"

        full_prompt = f"{system_prompt}\n{history_text}\nStudent (teaching you): {user_message}"

        model = get_gemini_model()
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.8, max_output_tokens=4096
                ),
            )
            return response.text
        except Exception as e:
            logger.error("protege_reason_failed", error=str(e))
            return "Hmm, I got a bit confused there. Could you try explaining that part again?"

    async def assess_understanding(
        self, state: AgentState, response: str
    ) -> list[dict]:
        agent_ctx = state.get("metadata", {}).get("agent_context", {})
        exchange_count = agent_ctx.get("exchange_count", 0)
        max_exchanges = agent_ctx.get("max_exchanges", 7)

        messages = state.get("messages", [])
        user_message = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")

        should_evaluate = (
            exchange_count >= max_exchanges
            or any(kw in user_message.lower() for kw in ["how did i do", "evaluate", "end teaching", "stop teaching"])
        )

        if not should_evaluate:
            return []

        # Extract score from evaluation response
        score = 5
        score_match = re.search(r"\*\*Overall Score\*\*:\s*(\d+)/10", response)
        if score_match:
            score = int(score_match.group(1))

        # Map score to SM-2 quality
        if score >= 9:
            quality = 5
        elif score >= 7:
            quality = 4
        elif score >= 5:
            quality = 3
        elif score >= 3:
            quality = 2
        else:
            quality = 1

        # Attribute the score to whatever the student actually taught. Reading a
        # target_concept from the context would never match — nothing sets it.
        student_state = state.get("student_state", {})
        taught_text = " ".join(
            msg["content"]
            for msg in state.get("conversation_history", [])
            if msg["role"] == "user"
        )
        concept_ids = match_concepts_in_text(taught_text, student_state)
        if not concept_ids:
            return []

        state["concept_ids_touched"] = concept_ids
        return [{"concept_id": cid, "quality": quality} for cid in concept_ids]
