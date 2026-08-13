"""Auto-generate flashcards from conversations and manage SM-2 review."""

import json
import re
from datetime import datetime, timezone, timedelta

import structlog
import google.generativeai as genai
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flashcard import Flashcard
from app.services.llm import get_gemini_model
from app.services.student_state import sm2_update

logger = structlog.get_logger()

EXTRACTION_PROMPT = """You are an expert educator. Given this conversation between a tutor and student, extract the key facts as flashcards.

Conversation:
{conversation}

Create 3-6 flashcards. Each flashcard has a "front" (question) and "back" (answer).
Keep questions concise and answers factual. Focus on the core concepts discussed.

Return ONLY a JSON array:
[
  {{"front": "What is...?", "back": "It is..."}},
  ...
]"""


async def generate_flashcards_from_conversation(
    db: AsyncSession,
    student_id,
    conversation_text: str,
    subject_id=None,
    concept_id=None,
) -> list[dict]:
    """Use LLM to extract flashcards from a conversation."""
    model = get_gemini_model()
    prompt = EXTRACTION_PROMPT.format(conversation=conversation_text[-3000:])

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3, max_output_tokens=4096
            ),
        )
        raw = response.text.strip()
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if json_match:
            raw = json_match.group(1).strip()

        cards_data = json.loads(raw)
    except Exception as e:
        logger.error("flashcard_extraction_failed", error=str(e))
        return []

    now = datetime.now(timezone.utc)
    created = []
    for card in cards_data:
        if not card.get("front") or not card.get("back"):
            continue
        fc = Flashcard(
            student_id=student_id,
            concept_id=concept_id,
            subject_id=subject_id,
            front=card["front"],
            back=card["back"],
            source="auto",
            next_review_at=now + timedelta(days=1),
        )
        db.add(fc)
        await db.flush()
        created.append({
            "id": str(fc.id),
            "front": fc.front,
            "back": fc.back,
            "source": fc.source,
        })

    await db.commit()
    logger.info("flashcards_generated", count=len(created), student_id=str(student_id))
    return created


async def get_flashcards(
    db: AsyncSession, student_id, subject_id=None, due_only: bool = False
) -> list[dict]:
    """Get flashcards for a student, optionally filtered."""
    query = select(Flashcard).where(Flashcard.student_id == student_id)
    if subject_id:
        query = query.where(Flashcard.subject_id == subject_id)
    if due_only:
        now = datetime.now(timezone.utc)
        query = query.where(
            (Flashcard.next_review_at <= now) | (Flashcard.next_review_at.is_(None))
        )
    query = query.order_by(Flashcard.next_review_at.asc().nullsfirst())

    result = await db.execute(query)
    cards = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "front": c.front,
            "back": c.back,
            "source": c.source,
            "concept_id": str(c.concept_id) if c.concept_id else None,
            "subject_id": str(c.subject_id) if c.subject_id else None,
            "easiness_factor": c.easiness_factor,
            "interval_days": c.interval_days,
            "repetitions": c.repetitions,
            "next_review_at": c.next_review_at.isoformat() if c.next_review_at else None,
            "last_reviewed_at": c.last_reviewed_at.isoformat() if c.last_reviewed_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cards
    ]


async def review_flashcard(
    db: AsyncSession, student_id, flashcard_id, quality: int
) -> dict:
    """Review a flashcard with a quality rating (1-5), update SM-2 schedule."""
    result = await db.execute(
        select(Flashcard).where(
            Flashcard.id == flashcard_id,
            Flashcard.student_id == student_id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise ValueError("Flashcard not found")

    new_easiness, new_interval, new_reps = sm2_update(
        quality=quality,
        easiness=card.easiness_factor,
        interval=card.interval_days,
        repetitions=card.repetitions,
    )

    now = datetime.now(timezone.utc)
    card.easiness_factor = new_easiness
    card.interval_days = new_interval
    card.repetitions = new_reps
    card.last_reviewed_at = now
    card.next_review_at = now + timedelta(days=new_interval)

    await db.commit()

    return {
        "id": str(card.id),
        "easiness_factor": new_easiness,
        "interval_days": new_interval,
        "repetitions": new_reps,
        "next_review_at": card.next_review_at.isoformat(),
    }


async def create_manual_flashcard(
    db: AsyncSession, student_id, front: str, back: str,
    subject_id=None, concept_id=None,
) -> dict:
    now = datetime.now(timezone.utc)
    card = Flashcard(
        student_id=student_id,
        concept_id=concept_id,
        subject_id=subject_id,
        front=front,
        back=back,
        source="manual",
        next_review_at=now + timedelta(days=1),
    )
    db.add(card)
    await db.commit()
    return {
        "id": str(card.id),
        "front": card.front,
        "back": card.back,
        "source": "manual",
    }


async def get_flashcard_stats(db: AsyncSession, student_id) -> dict:
    now = datetime.now(timezone.utc)
    total = await db.execute(
        select(func.count()).select_from(Flashcard).where(
            Flashcard.student_id == student_id
        )
    )
    due = await db.execute(
        select(func.count()).select_from(Flashcard).where(
            Flashcard.student_id == student_id,
            Flashcard.next_review_at <= now,
        )
    )
    mastered = await db.execute(
        select(func.count()).select_from(Flashcard).where(
            Flashcard.student_id == student_id,
            Flashcard.repetitions >= 5,
        )
    )
    return {
        "total": total.scalar() or 0,
        "due_now": due.scalar() or 0,
        "mastered": mastered.scalar() or 0,
    }
