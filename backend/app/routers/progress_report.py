"""Progress report PDF export endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.subject import Subject
from app.models.student import Enrollment
from app.services.progress_report import generate_progress_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/progress/{subject_id}")
async def download_progress_report(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download a PDF progress report for a subject."""
    # Verify enrollment
    enrollment = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == user.id,
            Enrollment.subject_id == subject_id,
        )
    )
    if not enrollment.scalar_one_or_none():
        raise HTTPException(403, "Not enrolled in this subject")

    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(404, "Subject not found")

    pdf_bytes = await generate_progress_pdf(
        db, user.id, subject_id,
        student_name=user.full_name,
        subject_name=subject.name,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="EduAgent_Progress_{subject.code}.pdf"'
        },
    )
