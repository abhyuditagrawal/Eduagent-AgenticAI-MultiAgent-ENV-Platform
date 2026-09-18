"""Collaborative annotation of course materials (Future Work item #9).

A student pins a note to a specific page of a subject's source material.
Persisted so it outlives the study room session that produced it; a live
study room additionally broadcasts new annotations over the existing
study-room WebSocket (see ws_study.py's "annotation" message type) so
everyone currently in the room sees it appear immediately, on top of the
REST list used to load a page's existing annotations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.annotation import MaterialAnnotation

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class AnnotationCreateRequest(BaseModel):
    subject_id: str
    source_file: str
    page: int = 0
    note: str
    highlight_text: str | None = None
    room_id: str | None = None


@router.get("")
async def list_annotations(
    subject_id: str,
    source_file: str | None = None,
    page: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List annotations for a subject, optionally narrowed to one page."""
    query = select(MaterialAnnotation, User.full_name, User.email).join(
        User, MaterialAnnotation.author_id == User.id
    ).where(MaterialAnnotation.subject_id == uuid.UUID(subject_id))

    if source_file:
        query = query.where(MaterialAnnotation.source_file == source_file)
    if page is not None:
        query = query.where(MaterialAnnotation.page == page)

    query = query.order_by(MaterialAnnotation.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": str(a.id),
            "subject_id": str(a.subject_id),
            "source_file": a.source_file,
            "page": a.page,
            "note": a.note,
            "highlight_text": a.highlight_text,
            "author_id": str(a.author_id),
            "author_name": name,
            "author_email": email,
            "room_id": str(a.room_id) if a.room_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a, name, email in rows
    ]


@router.post("", status_code=201)
async def create_annotation(
    req: AnnotationCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    annotation = MaterialAnnotation(
        subject_id=uuid.UUID(req.subject_id),
        author_id=user.id,
        room_id=uuid.UUID(req.room_id) if req.room_id else None,
        source_file=req.source_file,
        page=req.page,
        note=req.note,
        highlight_text=req.highlight_text,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)

    return {
        "id": str(annotation.id),
        "subject_id": str(annotation.subject_id),
        "source_file": annotation.source_file,
        "page": annotation.page,
        "note": annotation.note,
        "highlight_text": annotation.highlight_text,
        "author_id": str(annotation.author_id),
        "author_name": user.full_name,
        "room_id": str(annotation.room_id) if annotation.room_id else None,
        "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
    }


@router.delete("/{annotation_id}")
async def delete_annotation(
    annotation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    annotation = await db.get(MaterialAnnotation, uuid.UUID(annotation_id))
    if not annotation:
        raise HTTPException(404, "Annotation not found")
    if annotation.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "You can only delete your own annotations")

    await db.delete(annotation)
    await db.commit()
    return {"deleted": True}
