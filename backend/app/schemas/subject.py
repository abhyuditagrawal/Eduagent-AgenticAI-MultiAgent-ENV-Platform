import uuid
from datetime import datetime
from pydantic import BaseModel


class SubjectResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
