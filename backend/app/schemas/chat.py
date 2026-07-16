import uuid
from datetime import datetime
from pydantic import BaseModel


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


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None = None
    agent_type: str | None = None
    subject_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
