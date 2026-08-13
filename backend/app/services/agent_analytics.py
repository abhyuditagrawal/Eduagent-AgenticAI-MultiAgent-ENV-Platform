"""Agent performance logging and analytics service."""

import time
import uuid
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select, func, case, distinct, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AgentLog, LearningEvent
from app.models.user import User

logger = structlog.get_logger()


async def log_agent_invocation(
    db: AsyncSession,
    student_id,
    conversation_id,
    agent_type: str,
    intent: str,
    response_time_ms: int,
    rag_chunks_used: int = 0,
    success: bool = True,
    error_message: str | None = None,
):
    log = AgentLog(
        student_id=student_id,
        conversation_id=conversation_id,
        agent_type=agent_type,
        intent=intent,
        response_time_ms=response_time_ms,
        rag_chunks_used=rag_chunks_used,
        success=success,
        error_message=error_message,
    )
    db.add(log)
    await db.flush()
    return log


async def log_learning_event(
    db: AsyncSession,
    student_id,
    event_type: str,
    concept_id=None,
    subject_id=None,
    agent_type: str | None = None,
    data: dict | None = None,
):
    event = LearningEvent(
        student_id=student_id,
        event_type=event_type,
        concept_id=concept_id,
        subject_id=subject_id,
        agent_type=agent_type,
        data=data or {},
    )
    db.add(event)
    await db.flush()
    return event


async def get_agent_analytics(db: AsyncSession, days: int = 30) -> dict:
    """Get aggregated agent performance analytics (admin view)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Agent usage distribution
    usage_result = await db.execute(
        select(
            AgentLog.agent_type,
            func.count().label("count"),
            func.avg(AgentLog.response_time_ms).label("avg_response_ms"),
            func.sum(case((AgentLog.success == True, 1), else_=0)).label("success_count"),
        )
        .where(AgentLog.created_at >= cutoff)
        .group_by(AgentLog.agent_type)
        .order_by(func.count().desc())
    )
    agent_stats = []
    for row in usage_result.all():
        agent_stats.append({
            "agent_type": row.agent_type,
            "total_invocations": row.count,
            "avg_response_time_ms": round(row.avg_response_ms or 0),
            "success_rate": round((row.success_count / row.count) * 100, 1) if row.count > 0 else 0,
        })

    # Intent distribution
    intent_result = await db.execute(
        select(AgentLog.intent, func.count().label("count"))
        .where(AgentLog.created_at >= cutoff)
        .group_by(AgentLog.intent)
        .order_by(func.count().desc())
    )
    intent_stats = [
        {"intent": row.intent, "count": row.count}
        for row in intent_result.all()
    ]

    # Daily request volume. The unit must be a SQL literal, not a bound parameter,
    # or Postgres cannot match the GROUP BY expression to the selected one.
    day = func.date_trunc(literal_column("'day'"), AgentLog.created_at)
    daily_result = await db.execute(
        select(day.label("day"), func.count().label("count"))
        .where(AgentLog.created_at >= cutoff)
        .group_by(day)
        .order_by(day)
    )
    daily_stats = [
        {"date": str(row.day.date()) if row.day else "", "requests": row.count}
        for row in daily_result.all()
    ]

    # Total stats
    total_result = await db.execute(
        select(
            func.count().label("total"),
            func.count(distinct(AgentLog.student_id)).label("unique_students"),
            func.avg(AgentLog.response_time_ms).label("avg_ms"),
        )
        .where(AgentLog.created_at >= cutoff)
    )
    total_row = total_result.one()

    return {
        "period_days": days,
        "total_invocations": total_row.total,
        "unique_students": total_row.unique_students,
        "avg_response_time_ms": round(total_row.avg_ms or 0),
        "agent_stats": agent_stats,
        "intent_distribution": intent_stats,
        "daily_volume": daily_stats,
    }


async def get_class_analytics(db: AsyncSession) -> dict:
    """Get class-level aggregated analytics (admin view)."""
    from app.models.student import StudentConcept, Enrollment
    from app.models.concept import Concept
    from app.models.subject import Subject

    # Overall class mastery by subject
    subject_result = await db.execute(
        select(
            Subject.id,
            Subject.name,
            Subject.code,
            func.count(distinct(Enrollment.student_id)).label("enrolled"),
            func.avg(StudentConcept.confidence_score).label("avg_mastery"),
        )
        .outerjoin(Enrollment, Subject.id == Enrollment.subject_id)
        .outerjoin(Concept, Subject.id == Concept.subject_id)
        .outerjoin(
            StudentConcept,
            (Concept.id == StudentConcept.concept_id),
        )
        .group_by(Subject.id, Subject.name, Subject.code)
    )
    subjects = []
    for row in subject_result.all():
        subjects.append({
            "subject_id": str(row.id),
            "subject_name": row.name,
            "subject_code": row.code,
            "enrolled_students": row.enrolled,
            "avg_mastery": round((row.avg_mastery or 0) * 100, 1),
        })

    # Top weak concepts across all students
    weak_result = await db.execute(
        select(
            Concept.name,
            Subject.code,
            func.avg(StudentConcept.confidence_score).label("avg_conf"),
            func.count(distinct(StudentConcept.student_id)).label("student_count"),
        )
        .join(Concept, StudentConcept.concept_id == Concept.id)
        .join(Subject, Concept.subject_id == Subject.id)
        .group_by(Concept.name, Subject.code)
        .having(func.avg(StudentConcept.confidence_score) < 0.5)
        .order_by(func.avg(StudentConcept.confidence_score).asc())
        .limit(15)
    )
    weak_concepts = [
        {
            "concept": row.name,
            "subject": row.code,
            "avg_confidence": round((row.avg_conf or 0) * 100, 1),
            "students_struggling": row.student_count,
        }
        for row in weak_result.all()
    ]

    # Total platform stats
    total_students = await db.execute(
        select(func.count()).select_from(User).where(User.role == "student")
    )
    student_count = total_students.scalar() or 0

    total_interactions = await db.execute(
        select(func.count()).select_from(AgentLog)
    )
    interaction_count = total_interactions.scalar() or 0

    return {
        "total_students": student_count,
        "total_interactions": interaction_count,
        "subjects": subjects,
        "top_weak_concepts": weak_concepts,
    }


async def get_learning_path(db: AsyncSession, student_id, subject_id=None) -> list[dict]:
    """Get chronological learning events for a student."""
    query = (
        select(LearningEvent)
        .where(LearningEvent.student_id == student_id)
        .order_by(LearningEvent.created_at.asc())
    )
    if subject_id:
        query = query.where(LearningEvent.subject_id == subject_id)

    result = await db.execute(query.limit(200))
    events = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "concept_id": str(e.concept_id) if e.concept_id else None,
            "subject_id": str(e.subject_id) if e.subject_id else None,
            "agent_type": e.agent_type,
            "data": e.data,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]
