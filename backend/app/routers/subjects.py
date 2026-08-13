from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.subject import Subject
from app.models.student import Enrollment
from app.models.user import User
from app.schemas.subject import SubjectResponse, SubjectCreate
from app.services.student_state import sync_student_concepts

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
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid as _uuid

    sid = _uuid.UUID(subject_id)

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
