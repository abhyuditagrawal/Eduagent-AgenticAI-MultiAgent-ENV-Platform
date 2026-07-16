from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept
from app.models.student import Enrollment, StudentConcept
from app.models.subject import Subject

logger = structlog.get_logger()


async def generate_nudges(db: AsyncSession, student_id) -> list[dict]:
    now = datetime.now(timezone.utc)
    nudges = []

    # Get all enrolled subjects
    result = await db.execute(
        select(Enrollment, Subject)
        .join(Subject, Enrollment.subject_id == Subject.id)
        .where(Enrollment.student_id == student_id)
    )
    enrollments = result.all()

    for enrollment, subject in enrollments:
        # 1. Find overdue reviews
        overdue_result = await db.execute(
            select(StudentConcept, Concept)
            .join(Concept, StudentConcept.concept_id == Concept.id)
            .where(
                StudentConcept.student_id == student_id,
                Concept.subject_id == subject.id,
                StudentConcept.next_review_at < now,
            )
            .order_by(StudentConcept.next_review_at.asc())
            .limit(3)
        )
        overdue_rows = overdue_result.all()

        for sc, concept in overdue_rows:
            days_overdue = (now - sc.next_review_at).days if sc.next_review_at else 0
            if days_overdue >= 1:
                nudges.append(
                    {
                        "type": "review_overdue",
                        "concept_name": concept.name,
                        "concept_id": str(concept.id),
                        "subject": subject.name,
                        "subject_id": str(subject.id),
                        "message": (
                            f"You haven't reviewed '{concept.name}' in {days_overdue} day(s). "
                            f"Quick refresher?"
                        ),
                        "priority": "high" if days_overdue >= 3 else "medium",
                        "action": "start_review",
                    }
                )

        # 2. Check for subjects not studied recently
        recent_result = await db.execute(
            select(StudentConcept)
            .join(Concept, StudentConcept.concept_id == Concept.id)
            .where(
                StudentConcept.student_id == student_id,
                Concept.subject_id == subject.id,
                StudentConcept.last_seen_at.isnot(None),
            )
            .order_by(StudentConcept.last_seen_at.desc())
            .limit(1)
        )
        latest = recent_result.scalar_one_or_none()

        if latest and latest.last_seen_at:
            days_since = (now - latest.last_seen_at).days
            if days_since >= 3:
                nudges.append(
                    {
                        "type": "subject_inactive",
                        "concept_name": "",
                        "concept_id": "",
                        "subject": subject.name,
                        "subject_id": str(subject.id),
                        "message": (
                            f"You haven't studied {subject.name} in {days_since} days. "
                            f"Let's pick up where you left off!"
                        ),
                        "priority": "medium",
                        "action": "resume_study",
                    }
                )

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    nudges.sort(key=lambda n: priority_order.get(n["priority"], 2))

    return nudges[:10]
