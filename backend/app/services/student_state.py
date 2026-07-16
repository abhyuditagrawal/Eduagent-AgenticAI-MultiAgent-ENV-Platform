from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept, ConceptPrerequisite
from app.models.student import StudentConcept
from app.services.knowledge_tracing import (
    bkt_update,
    update_memory_stability,
    days_until_forgetting,
    BKT_P_L0,
)

logger = structlog.get_logger()


def sm2_update(quality: int, easiness: float, interval: float, repetitions: int):
    if quality >= 3:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = interval * easiness
        new_repetitions = repetitions + 1
    else:
        new_interval = 1
        new_repetitions = 0

    new_easiness = max(
        1.3, easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    )
    return new_easiness, new_interval, new_repetitions


async def get_student_state(db: AsyncSession, student_id, subject_id) -> dict:
    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            Concept.subject_id == subject_id,
        )
    )
    rows = result.all()

    state = {}
    for sc, concept in rows:
        state[str(concept.id)] = {
            "concept_id": str(concept.id),
            "concept_name": concept.name,
            "confidence": sc.confidence_score,
            "attempts": sc.attempts,
            "correct_count": sc.correct_count,
            "last_seen": sc.last_seen_at.isoformat() if sc.last_seen_at else None,
            "next_review": sc.next_review_at.isoformat() if sc.next_review_at else None,
            "difficulty_tier": concept.difficulty_tier,
            "chapter": concept.chapter,
        }
    return state


async def update_concept_confidence(
    db: AsyncSession, student_id, concept_id, quality: int
):
    quality = max(0, min(5, quality))

    result = await db.execute(
        select(StudentConcept).where(
            StudentConcept.student_id == student_id,
            StudentConcept.concept_id == concept_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        logger.warning(
            "student_concept_not_found",
            student_id=str(student_id),
            concept_id=str(concept_id),
        )
        return

    repetitions = sc.correct_count if quality >= 3 else 0
    new_easiness, new_interval, new_repetitions = sm2_update(
        quality, sc.easiness_factor, sc.interval_days, repetitions
    )

    sc.easiness_factor = new_easiness
    sc.interval_days = new_interval
    sc.attempts += 1
    if quality >= 3:
        sc.correct_count += 1
    sc.confidence_score = min(1.0, max(0.0, quality / 5.0))
    now = datetime.now(timezone.utc)
    sc.last_seen_at = now
    sc.next_review_at = now + timedelta(days=new_interval)

    # --- Bayesian Knowledge Tracing + predictive forgetting update ---
    correct = quality >= 3
    concept = await db.get(Concept, concept_id)
    difficulty = concept.difficulty_tier if concept else 1
    prior = sc.bkt_mastery if sc.bkt_mastery is not None else BKT_P_L0
    sc.bkt_mastery = bkt_update(prior, correct, difficulty)
    sc.memory_stability = update_memory_stability(
        sc.memory_stability or 1.0, sc.bkt_mastery, correct
    )
    sc.predicted_forget_at = now + timedelta(
        days=days_until_forgetting(sc.memory_stability)
    )

    await db.commit()

    logger.info(
        "confidence_updated",
        student_id=str(student_id),
        concept_id=str(concept_id),
        quality=quality,
        new_confidence=sc.confidence_score,
        bkt_mastery=round(sc.bkt_mastery, 3),
    )


async def get_weak_concepts(
    db: AsyncSession, student_id, subject_id, threshold: float = 0.4
) -> list[dict]:
    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            Concept.subject_id == subject_id,
            StudentConcept.confidence_score < threshold,
        )
        .order_by(StudentConcept.confidence_score.asc())
    )
    rows = result.all()

    return [
        {
            "concept_id": str(concept.id),
            "concept_name": concept.name,
            "confidence": sc.confidence_score,
            "difficulty_tier": concept.difficulty_tier,
            "chapter": concept.chapter,
        }
        for sc, concept in rows
    ]


async def get_prerequisite_gaps(
    db: AsyncSession, student_id, concept_id, threshold: float = 0.5
) -> list[dict]:
    result = await db.execute(
        select(ConceptPrerequisite).where(
            ConceptPrerequisite.concept_id == concept_id
        )
    )
    prereq_edges = result.scalars().all()

    gaps = []
    for edge in prereq_edges:
        sc_result = await db.execute(
            select(StudentConcept).where(
                StudentConcept.student_id == student_id,
                StudentConcept.concept_id == edge.prerequisite_id,
            )
        )
        sc = sc_result.scalar_one_or_none()

        concept_result = await db.execute(
            select(Concept).where(Concept.id == edge.prerequisite_id)
        )
        prereq_concept = concept_result.scalar_one_or_none()

        if prereq_concept and (sc is None or sc.confidence_score < threshold):
            gaps.append(
                {
                    "concept_id": str(prereq_concept.id),
                    "concept_name": prereq_concept.name,
                    "confidence": sc.confidence_score if sc else 0.0,
                    "strength": edge.strength,
                }
            )

    return gaps


async def get_overdue_concepts(
    db: AsyncSession, student_id, subject_id
) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            Concept.subject_id == subject_id,
            StudentConcept.next_review_at < now,
        )
        .order_by(StudentConcept.next_review_at.asc())
    )
    rows = result.all()

    return [
        {
            "concept_id": str(concept.id),
            "concept_name": concept.name,
            "confidence": sc.confidence_score,
            "next_review": sc.next_review_at.isoformat() if sc.next_review_at else None,
            "days_overdue": (now - sc.next_review_at).days if sc.next_review_at else 0,
            "chapter": concept.chapter,
        }
        for sc, concept in rows
    ]


async def get_mastery_summary(
    db: AsyncSession, student_id, subject_id
) -> dict:
    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            Concept.subject_id == subject_id,
        )
    )
    rows = result.all()

    now = datetime.now(timezone.utc)
    total = len(rows)
    mastered = sum(1 for sc, _ in rows if sc.confidence_score >= 0.8)
    proficient = sum(1 for sc, _ in rows if 0.5 <= sc.confidence_score < 0.8)
    developing = sum(1 for sc, _ in rows if 0.2 <= sc.confidence_score < 0.5)
    not_started = sum(1 for sc, _ in rows if sc.confidence_score < 0.2)
    overdue = sum(
        1
        for sc, _ in rows
        if sc.next_review_at and sc.next_review_at < now
    )

    overall = (
        sum(sc.confidence_score for sc, _ in rows) / total if total > 0 else 0.0
    )

    # Chapter-level aggregation
    chapter_scores: dict[str, list[float]] = {}
    for sc, concept in rows:
        ch = concept.chapter or "Uncategorized"
        chapter_scores.setdefault(ch, []).append(sc.confidence_score)

    chapter_avgs = {
        ch: sum(scores) / len(scores) for ch, scores in chapter_scores.items()
    }
    strongest = max(chapter_avgs, key=chapter_avgs.get, default="N/A") if chapter_avgs else "N/A"
    weakest = min(chapter_avgs, key=chapter_avgs.get, default="N/A") if chapter_avgs else "N/A"

    return {
        "total_concepts": total,
        "mastered": mastered,
        "proficient": proficient,
        "developing": developing,
        "not_started": not_started,
        "overdue_reviews": overdue,
        "overall_score": round(overall, 2),
        "strongest_chapter": strongest,
        "weakest_chapter": weakest,
    }


async def decay_confidence(db: AsyncSession, student_id):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(StudentConcept).where(
            StudentConcept.student_id == student_id,
            StudentConcept.next_review_at.isnot(None),
        )
    )
    all_sc = result.scalars().all()

    decayed = 0
    for sc in all_sc:
        if sc.next_review_at and sc.interval_days > 0:
            overdue_threshold = sc.next_review_at + timedelta(
                days=sc.interval_days
            )
            if now > overdue_threshold and sc.confidence_score > 0.05:
                sc.confidence_score = max(0.0, sc.confidence_score - 0.1)
                decayed += 1

    if decayed > 0:
        await db.commit()
        logger.info(
            "confidence_decay_applied",
            student_id=str(student_id),
            decayed_count=decayed,
        )

    return decayed


async def get_study_priority_queue(
    db: AsyncSession, student_id, subject_id
) -> list[dict]:
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == student_id,
            Concept.subject_id == subject_id,
        )
    )
    rows = result.all()

    priorities = []
    for sc, concept in rows:
        score = 0
        reason = ""
        action = "review"

        # Overdue reviews get highest priority
        if sc.next_review_at and sc.next_review_at < now:
            days_overdue = (now - sc.next_review_at).days
            score += 100 + days_overdue * 10
            reason = f"Overdue by {days_overdue} day(s)"
            action = "review_overdue"
        # Low confidence
        elif sc.confidence_score < 0.3:
            score += 80
            reason = "Low confidence — needs reinforcement"
            action = "strengthen"
        elif sc.confidence_score < 0.5:
            score += 50
            reason = "Developing — could use more practice"
            action = "practice"

        # Boost high-difficulty concepts
        score += concept.difficulty_tier * 5

        if score > 0:
            priorities.append(
                {
                    "concept_id": str(concept.id),
                    "concept_name": concept.name,
                    "confidence": sc.confidence_score,
                    "chapter": concept.chapter,
                    "priority_score": score,
                    "reason": reason,
                    "action": action,
                }
            )

    priorities.sort(key=lambda x: x["priority_score"], reverse=True)
    return priorities[:20]
