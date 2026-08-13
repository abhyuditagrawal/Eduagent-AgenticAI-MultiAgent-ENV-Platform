import uuid
from datetime import datetime, timezone, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chat import Conversation, Message
from app.models.concept import Concept, ConceptPrerequisite
from app.models.student import Enrollment, StudentConcept
from app.models.subject import Subject
from app.models.user import User
from app.services.student_state import (
    get_weak_concepts,
    get_overdue_concepts,
    get_prerequisite_gaps,
    get_mastery_summary,
    get_study_priority_queue,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# A gap longer than this ends a study session rather than counting as study time.
SESSION_IDLE_MINUTES = 30


def _measure_session_minutes(messages) -> dict[str, int]:
    """Study minutes per day, measured from real message timestamps."""
    per_day: dict[str, float] = {}
    session_start = None
    previous = None

    def close_session():
        if session_start is None or previous is None:
            return
        day_key = session_start.strftime("%Y-%m-%d")
        elapsed = (previous - session_start).total_seconds() / 60
        per_day[day_key] = per_day.get(day_key, 0.0) + elapsed

    for msg in messages:
        ts = msg.created_at
        if previous is None:
            session_start = ts
        elif (ts - previous).total_seconds() / 60 > SESSION_IDLE_MINUTES:
            close_session()
            session_start = ts
        previous = ts
    close_session()

    return {day: int(round(minutes)) for day, minutes in per_day.items()}


def _status_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "mastered"
    elif confidence >= 0.5:
        return "proficient"
    elif confidence >= 0.2:
        return "developing"
    return "not_started"


@router.get("/mastery")
async def get_mastery(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)
    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == current_user.id,
            Concept.subject_id == sid,
        )
        .order_by(Concept.chapter, Concept.name)
    )
    rows = result.all()

    chapters: dict[str, list] = {}
    total_conf = 0.0
    for sc, concept in rows:
        ch = concept.chapter or "Uncategorized"
        chapters.setdefault(ch, [])
        conf = sc.confidence_score
        total_conf += conf
        chapters[ch].append({
            "id": str(concept.id),
            "name": concept.name,
            "confidence": round(conf, 2),
            "attempts": sc.attempts,
            "last_seen": sc.last_seen_at.isoformat() if sc.last_seen_at else None,
            "next_review": sc.next_review_at.isoformat() if sc.next_review_at else None,
            "status": _status_label(conf),
        })

    overall = round(total_conf / len(rows), 2) if rows else 0.0

    chapter_data = []
    for ch_name, concepts_list in chapters.items():
        avg = sum(c["confidence"] for c in concepts_list) / len(concepts_list) if concepts_list else 0.0
        chapter_data.append({
            "name": ch_name,
            "average_confidence": round(avg, 2),
            "concepts": concepts_list,
        })

    return {
        "subject": {"id": str(subject.id), "name": subject.name, "code": subject.code},
        "overall_score": overall,
        "chapters": chapter_data,
    }


@router.get("/weak-points")
async def get_weak_points_dashboard(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)

    weak = await get_weak_concepts(db, current_user.id, sid, threshold=0.5)
    overdue = await get_overdue_concepts(db, current_user.id, sid)
    overdue_ids = {o["concept_id"] for o in overdue}

    # Total concepts
    total_result = await db.execute(
        select(func.count()).select_from(Concept).where(Concept.subject_id == sid)
    )
    total_concepts = total_result.scalar() or 0

    enriched = []
    for w in weak:
        gaps = await get_prerequisite_gaps(db, current_user.id, uuid.UUID(w["concept_id"]))
        gap_names = [g["concept_name"] for g in gaps]

        if gaps:
            reason = "prerequisite_gap"
            suggestion = f"Review {', '.join(gap_names[:3])} first, then revisit {w['concept_name']}"
        elif w["concept_id"] in overdue_ids:
            reason = "overdue_review"
            suggestion = f"You haven't reviewed {w['concept_name']} in a while. Quick refresher recommended."
        else:
            reason = "low_confidence"
            suggestion = f"Practice more with {w['concept_name']} — try teaching it or doing practice questions."

        priority = "high" if w["confidence"] < 0.2 else "medium" if w["confidence"] < 0.35 else "low"

        days_since_review = None
        if w.get("last_seen"):
            last_seen = datetime.fromisoformat(w["last_seen"])
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            days_since_review = (datetime.now(timezone.utc) - last_seen).days

        enriched.append({
            "concept": {
                "id": w["concept_id"],
                "name": w["concept_name"],
                "chapter": w.get("chapter", ""),
            },
            "confidence": w["confidence"],
            "reason": reason,
            "missing_prerequisites": gap_names,
            "suggestion": suggestion,
            "days_since_review": days_since_review,
            "priority": priority,
        })

    return {
        "weak_concepts": enriched,
        "total_weak": len(enriched),
        "total_concepts": total_concepts,
    }


@router.get("/exam-readiness")
async def get_exam_readiness(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)

    result = await db.execute(
        select(StudentConcept, Concept)
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .where(
            StudentConcept.student_id == current_user.id,
            Concept.subject_id == sid,
        )
    )
    rows = result.all()

    if not rows:
        return {
            "overall_readiness": 0.0,
            "readiness_label": "Not Started",
            "by_difficulty": {"foundational": 0.0, "intermediate": 0.0, "advanced": 0.0},
            "high_risk_topics": [],
            "strengths": [],
            "recommended_study_hours": 0,
            "study_plan": [],
        }

    # Group by difficulty
    diff_groups: dict[str, list[float]] = {"foundational": [], "intermediate": [], "advanced": []}
    high_risk = []
    strengths = []

    for sc, concept in rows:
        conf = sc.confidence_score
        tier = concept.difficulty_tier
        if tier <= 1:
            diff_groups["foundational"].append(conf)
        elif tier <= 2:
            diff_groups["intermediate"].append(conf)
        else:
            diff_groups["advanced"].append(conf)

        if conf < 0.4:
            high_risk.append({
                "name": concept.name,
                "confidence": round(conf, 2),
                "difficulty": tier,
                "impact": "high" if tier >= 3 else "medium",
            })
        elif conf >= 0.8:
            strengths.append({
                "name": concept.name,
                "confidence": round(conf, 2),
                "difficulty": tier,
            })

    by_diff = {}
    for k, v in diff_groups.items():
        by_diff[k] = round(sum(v) / len(v), 2) if v else 0.0

    overall = sum(sc.confidence_score for sc, _ in rows) / len(rows)

    if overall >= 0.8:
        label = "Well Prepared"
    elif overall >= 0.6:
        label = "Moderately Prepared"
    elif overall >= 0.4:
        label = "Needs More Study"
    else:
        label = "At Risk"

    # Simple study plan from priority queue
    priority_queue = await get_study_priority_queue(db, current_user.id, sid)
    study_plan = []
    hours_total = 0
    for i, item in enumerate(priority_queue[:7]):
        hours = 3 if item["confidence"] < 0.2 else 2 if item["confidence"] < 0.4 else 1
        hours_total += hours
        study_plan.append({
            "day": i + 1,
            "focus": item["concept_name"],
            "duration_hours": hours,
            "reason": item["reason"],
        })

    high_risk.sort(key=lambda x: x["confidence"])

    return {
        "overall_readiness": round(overall, 2),
        "readiness_label": label,
        "by_difficulty": by_diff,
        "high_risk_topics": high_risk[:10],
        "strengths": strengths[:10],
        "recommended_study_hours": hours_total,
        "study_plan": study_plan,
    }


@router.get("/activity")
async def get_activity(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Get messages in date range
    result = await db.execute(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.student_id == current_user.id,
            Message.created_at >= start_date,
        )
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    # Aggregate by day
    daily: dict[str, dict] = {}
    for msg in messages:
        day_key = msg.created_at.strftime("%Y-%m-%d")
        if day_key not in daily:
            daily[day_key] = {
                "date": day_key,
                "messages_sent": 0,
                "concepts_reviewed": 0,
                "agents_used": {},
                "confidence_gained": 0.0,
                "time_spent_minutes": 0,
            }

        daily[day_key]["messages_sent"] += 1

        if msg.agent_type:
            agents = daily[day_key]["agents_used"]
            agents[msg.agent_type] = agents.get(msg.agent_type, 0) + 1

        meta = msg.metadata_ or {}
        concepts = meta.get("concepts_touched", [])
        daily[day_key]["concepts_reviewed"] += len(concepts)

        updates = meta.get("confidence_updates", [])
        for u in updates:
            daily[day_key]["confidence_gained"] += u.get("quality", 0) * 0.02

    # Measure real study time from message timestamps: consecutive messages less
    # than SESSION_IDLE_MINUTES apart belong to one study session, and a session
    # lasts from its first to its last message.
    for day_key, minutes in _measure_session_minutes(messages).items():
        if day_key in daily:
            daily[day_key]["time_spent_minutes"] = minutes

    daily_list = sorted(daily.values(), key=lambda x: x["date"])

    # Streak calculation
    active_dates = set(daily.keys())
    current_streak = 0
    d = now.date()
    while d.strftime("%Y-%m-%d") in active_dates:
        current_streak += 1
        d -= timedelta(days=1)

    # Longest streak
    all_dates = sorted(active_dates)
    longest = 0
    cur = 0
    for i, date_str in enumerate(all_dates):
        if i == 0:
            cur = 1
        else:
            prev = datetime.strptime(all_dates[i - 1], "%Y-%m-%d").date()
            curr = datetime.strptime(date_str, "%Y-%m-%d").date()
            if (curr - prev).days == 1:
                cur += 1
            else:
                cur = 1
        longest = max(longest, cur)

    # Mastered concepts
    mastered_result = await db.execute(
        select(func.count())
        .select_from(StudentConcept)
        .where(
            StudentConcept.student_id == current_user.id,
            StudentConcept.confidence_score >= 0.8,
        )
    )
    total_mastered = mastered_result.scalar() or 0

    total_messages = sum(d["messages_sent"] for d in daily_list)
    total_minutes = sum(d["time_spent_minutes"] for d in daily_list)

    return {
        "daily_activity": daily_list,
        "streak": {
            "current": current_streak,
            "longest": longest,
            "total_days_active": len(active_dates),
        },
        "totals": {
            "total_messages": total_messages,
            "total_concepts_mastered": total_mastered,
            "total_study_hours": round(total_minutes / 60, 1),
        },
    }


@router.get("/concept-graph")
async def get_concept_graph_with_mastery(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)

    # Get concepts with student confidence
    result = await db.execute(
        select(Concept, StudentConcept)
        .outerjoin(
            StudentConcept,
            (StudentConcept.concept_id == Concept.id)
            & (StudentConcept.student_id == current_user.id),
        )
        .where(Concept.subject_id == sid)
    )
    rows = result.all()

    nodes = []
    concept_ids = []
    for concept, sc in rows:
        conf = sc.confidence_score if sc else 0.0
        nodes.append({
            "id": str(concept.id),
            "name": concept.name,
            "chapter": concept.chapter,
            "difficulty": concept.difficulty_tier,
            "confidence": round(conf, 2),
            "status": _status_label(conf),
            "x": None,
            "y": None,
        })
        concept_ids.append(concept.id)

    edges = []
    if concept_ids:
        edge_result = await db.execute(
            select(ConceptPrerequisite).where(
                ConceptPrerequisite.concept_id.in_(concept_ids)
            )
        )
        prereqs = edge_result.scalars().all()
        edges = [
            {
                "source": str(p.prerequisite_id),
                "target": str(p.concept_id),
                "strength": p.strength,
            }
            for p in prereqs
        ]

    return {"nodes": nodes, "edges": edges}
