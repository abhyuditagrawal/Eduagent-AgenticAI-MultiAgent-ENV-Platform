import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None
    agent_override: str | None = None
    subject_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: uuid.UUID
    agent_type: str | None = None
    metadata: dict = {}


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    agent_type: str | None = None
    metadata: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    """Rename a conversation. Titles are auto-generated from the first message,
    so this is the only way to give a long-running chat a meaningful name."""

    title: str = Field(min_length=1, max_length=255)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None = None
    agent_type: str | None = None
    subject_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
