from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.concept import Concept
from app.models.subject import Subject
from app.models.student import Enrollment, StudentConcept
from app.models.user import User
from app.schemas.subject import SubjectResponse, SubjectCreate

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
    _: User = Depends(get_admin_user),
):
    existing = await db.execute(select(Subject).where(Subject.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject with this code already exists",
        )

    subject = Subject(code=data.code, name=data.name, description=data.description)
    db.add(subject)
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
    await db.flush()

    # Auto-create student_concepts rows for all concepts in this subject
    concepts_result = await db.execute(
        select(Concept).where(Concept.subject_id == sid)
    )
    concepts = concepts_result.scalars().all()
    for concept in concepts:
        sc = StudentConcept(
            student_id=current_user.id,
            concept_id=concept.id,
        )
        db.add(sc)

    await db.commit()
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
