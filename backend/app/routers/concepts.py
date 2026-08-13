import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.concept import Concept, ConceptPrerequisite
from app.models.subject import Subject
from app.models.user import User
from app.schemas.concept import (
    ConceptResponse,
    ConceptGraphResponse,
    ConceptNodeResponse,
    ConceptEdgeResponse,
    ConceptPopulateRequest,
    ConceptCreate,
)
from app.services.concept_graph import extract_concepts_from_syllabus
from app.services.student_state import sync_student_concepts

router = APIRouter(prefix="/api/concepts", tags=["concepts"])


@router.get("/{subject_id}", response_model=list[ConceptResponse])
async def list_concepts(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)
    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    result = await db.execute(
        select(Concept).where(Concept.subject_id == sid).order_by(Concept.name)
    )
    concepts = result.scalars().all()
    return [ConceptResponse.model_validate(c) for c in concepts]


@router.get("/{subject_id}/graph", response_model=ConceptGraphResponse)
async def get_concept_graph(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)

    result = await db.execute(
        select(Concept).where(Concept.subject_id == sid)
    )
    concepts = result.scalars().all()

    nodes = [
        ConceptNodeResponse(
            id=str(c.id),
            name=c.name,
            difficulty=c.difficulty_tier,
            chapter=c.chapter,
        )
        for c in concepts
    ]

    concept_ids = [c.id for c in concepts]
    edges = []
    if concept_ids:
        edge_result = await db.execute(
            select(ConceptPrerequisite).where(
                ConceptPrerequisite.concept_id.in_(concept_ids)
            )
        )
        prereqs = edge_result.scalars().all()
        edges = [
            ConceptEdgeResponse(
                source=str(p.prerequisite_id),
                target=str(p.concept_id),
                strength=p.strength,
            )
            for p in prereqs
        ]

    return ConceptGraphResponse(nodes=nodes, edges=edges)


@router.post("/{subject_id}/populate")
async def populate_concepts(
    subject_id: str,
    data: ConceptPopulateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    sid = uuid.UUID(subject_id)
    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    try:
        concepts = await extract_concepts_from_syllabus(db, sid, data.syllabus_text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await sync_student_concepts(db, sid)
    return {"message": f"Extracted {len(concepts)} concepts", "count": len(concepts)}


@router.post("/{subject_id}", response_model=ConceptResponse, status_code=status.HTTP_201_CREATED)
async def create_concept(
    subject_id: str,
    data: ConceptCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Manually add a single concept, with optional prerequisites by name."""
    sid = uuid.UUID(subject_id)
    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    name = data.name.strip()
    existing = await db.execute(
        select(Concept).where(Concept.subject_id == sid, Concept.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A concept with this name already exists in this subject",
        )

    concept = Concept(
        subject_id=sid,
        name=name,
        description=data.description,
        difficulty_tier=data.difficulty_tier,
        chapter=data.chapter,
    )
    db.add(concept)
    await db.flush()

    if data.prerequisites:
        sibling_result = await db.execute(
            select(Concept).where(Concept.subject_id == sid)
        )
        by_name = {c.name: c for c in sibling_result.scalars().all()}
        for prereq_name in data.prerequisites:
            prereq = by_name.get(prereq_name)
            if prereq and prereq.id != concept.id:
                db.add(
                    ConceptPrerequisite(
                        concept_id=concept.id,
                        prerequisite_id=prereq.id,
                        strength=1.0,
                    )
                )

    await db.commit()
    await db.refresh(concept)

    await sync_student_concepts(db, sid)
    return ConceptResponse.model_validate(concept)
