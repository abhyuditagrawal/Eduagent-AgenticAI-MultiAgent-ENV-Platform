import uuid
from datetime import datetime
from pydantic import BaseModel


class ConceptResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    difficulty_tier: int = 1
    chapter: str | None = None
    subject_id: uuid.UUID

    model_config = {"from_attributes": True}


class ConceptNodeResponse(BaseModel):
    id: str
    name: str
    difficulty: int
    chapter: str | None = None


class ConceptEdgeResponse(BaseModel):
    source: str
    target: str
    strength: float


class ConceptGraphResponse(BaseModel):
    nodes: list[ConceptNodeResponse]
    edges: list[ConceptEdgeResponse]


class ConceptPopulateRequest(BaseModel):
    syllabus_text: str


class ConceptCreate(BaseModel):
    name: str
    description: str | None = None
    difficulty_tier: int = 1
    chapter: str | None = None
    prerequisites: list[str] = []
