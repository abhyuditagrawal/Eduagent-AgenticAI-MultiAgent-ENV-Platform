"""Flashcard endpoints: auto-generate from conversations, CRUD, SM-2 review."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.flashcard_service import (
    generate_flashcards_from_conversation,
    get_flashcards,
    review_flashcard,
    create_manual_flashcard,
    get_flashcard_stats,
)

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])


class GenerateRequest(BaseModel):
    conversation_text: str
    subject_id: str | None = None
    concept_id: str | None = None


class ReviewRequest(BaseModel):
    quality: int  # 1-5


class CreateRequest(BaseModel):
    front: str
    back: str
    subject_id: str | None = None
    concept_id: str | None = None


@router.post("/generate")
async def generate(
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cards = await generate_flashcards_from_conversation(
        db, user.id, req.conversation_text,
        subject_id=req.subject_id, concept_id=req.concept_id,
    )
    return {"flashcards": cards, "count": len(cards)}


@router.get("")
async def list_flashcards(
    subject_id: str | None = None,
    due_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_flashcards(db, user.id, subject_id=subject_id, due_only=due_only)


@router.post("/{flashcard_id}/review")
async def review(
    flashcard_id: str,
    req: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not 1 <= req.quality <= 5:
        raise HTTPException(400, "Quality must be 1-5")
    try:
        return await review_flashcard(db, user.id, flashcard_id, req.quality)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("")
async def create(
    req: CreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await create_manual_flashcard(
        db, user.id, req.front, req.back,
        subject_id=req.subject_id, concept_id=req.concept_id,
    )


@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_flashcard_stats(db, user.id)
