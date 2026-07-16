import uuid
from datetime import datetime
from pydantic import BaseModel


class IngestionResponse(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    filename: str
    status: str
    chunks: int
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
