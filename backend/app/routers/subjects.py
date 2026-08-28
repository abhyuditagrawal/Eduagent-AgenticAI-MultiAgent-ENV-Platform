import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chat import Conversation
from app.models.concept import Concept
from app.models.ingestion import IngestionJob
from app.models.subject import Subject
from app.models.student import Enrollment, StudentConcept
from app.models.user import User
from app.rag.vector_store import delete_collection
from app.schemas.subject import SubjectResponse, SubjectCreate
from app.services.student_state import sync_student_concepts

logger = structlog.get_logger()

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectResponse])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Subject).order_by(Subject.name))
    subjects = result.scalars().all()
    return [SubjectResponse.model_validate(s) for s in subjects]


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    data: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Students create their own subjects, then upload material for them."""
    code = data.code.strip().upper()
    existing = await db.execute(select(Subject).where(Subject.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject with this code already exists",
        )

    subject = Subject(code=code, name=data.name.strip(), description=data.description)
    db.add(subject)
    await db.flush()

    # Auto-enrol the creator so their tracking starts immediately
    db.add(Enrollment(student_id=current_user.id, subject_id=subject.id))

    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


@router.post("/{subject_id}/enroll", status_code=status.HTTP_201_CREATED)
async def enroll(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = subject_id

    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == current_user.id,
            Enrollment.subject_id == sid,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already enrolled"
        )

    enrollment = Enrollment(student_id=current_user.id, subject_id=sid)
    db.add(enrollment)
    await db.commit()

    # Create tracking rows for concepts that already exist; any added later are
    # backfilled by sync_student_concepts on the next read.
    await sync_student_concepts(db, sid, current_user.id)

    return {"message": "Enrolled successfully", "subject": subject.name}


@router.delete("/{subject_id}/enroll")
async def unenroll(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leave a subject, keeping it available to everyone else.

    Only this student's enrolment and their per-concept tracking rows go; the
    subject, its concepts and its uploaded material are untouched.
    """
    sid = subject_id

    result = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == current_user.id,
            Enrollment.subject_id == sid,
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="You are not enrolled in this subject"
        )

    concept_ids = (
        await db.execute(select(Concept.id).where(Concept.subject_id == sid))
    ).scalars().all()
    if concept_ids:
        await db.execute(
            delete(StudentConcept).where(
                StudentConcept.student_id == current_user.id,
                StudentConcept.concept_id.in_(concept_ids),
            )
        )

    await db.delete(enrollment)
    await db.commit()

    logger.info("unenrolled", student_id=str(current_user.id), subject_id=str(sid))
    return {"message": "Left the subject"}


@router.delete("/{subject_id}")
async def delete_subject(
    subject_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a subject along with its concepts and uploaded material.

    Permitted for an admin, or for a student who is the only one enrolled — so a
    subject created by mistake can be removed without letting one student
    destroy material other people are relying on.
    """
    sid = subject_id

    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    enrolled_ids = (
        await db.execute(
            select(Enrollment.student_id).where(Enrollment.subject_id == sid)
        )
    ).scalars().all()

    others = [uid for uid in enrolled_ids if uid != current_user.id]
    if current_user.role != "admin" and others:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{len(others)} other student(s) are enrolled in this subject. "
                "Leave it instead, or ask an admin to delete it."
            ),
        )

    # These two tables reference subjects without an ON DELETE rule, so the
    # delete below would fail on them. Conversations keep their history and just
    # lose the subject link; ingestion jobs describe the material being removed.
    await db.execute(
        update(Conversation)
        .where(Conversation.subject_id == sid)
        .values(subject_id=None)
    )
    await db.execute(delete(IngestionJob).where(IngestionJob.subject_id == sid))

    # Concepts, enrolments and study plans cascade; flashcards, learning events
    # and study rooms null out their subject reference.
    code = subject.code
    await db.delete(subject)
    await db.commit()

    # Only once the row is gone, so a failure here leaks a collection rather
    # than destroying vectors for a subject that still exists.
    try:
        dropped = delete_collection(f"subject_{code.lower()}")
        logger.info("subject_vectors_dropped", subject=code, existed=dropped)
    except Exception as e:
        logger.warning("subject_vector_cleanup_failed", subject=code, error=str(e))

    logger.info("subject_deleted", subject=code, by=str(current_user.id))
    return {"message": f"Deleted {subject.name}"}


@router.get("/enrolled", response_model=list[SubjectResponse])
async def list_enrolled(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Subject)
        .join(Enrollment, Enrollment.subject_id == Subject.id)
        .where(Enrollment.student_id == current_user.id)
        .order_by(Subject.name)
    )
    subjects = result.scalars().all()
    return [SubjectResponse.model_validate(s) for s in subjects]
