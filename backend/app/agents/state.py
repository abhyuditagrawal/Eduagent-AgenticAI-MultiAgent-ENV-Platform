from typing import TypedDict


class AgentState(TypedDict, total=False):
    messages: list
    student_id: str
    subject_id: str | None
    subject_code: str | None
    subject_name: str | None
    student_state: dict
    intent: str | None
    active_agent: str | None
    rag_context: list[dict]
    concept_ids_touched: list[str]
    concept_updates: list[dict]
    metadata: dict
    response: str
    conversation_history: list[dict]
