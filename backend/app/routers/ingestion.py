import os
import uuid
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ingestion import IngestionJob
from app.models.subject import Subject
from app.models.user import User
from app.schemas.ingestion import IngestionResponse
from app.services.ingestion import process_pdf

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


@router.post("/upload", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    subject_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are accepted"
        )

    sid = uuid.UUID(subject_id)
    subject = await db.get(Subject, sid)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job = IngestionJob(subject_id=sid, filename=file.filename)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(process_pdf, job.id, sid, file_path, file.filename)

    return IngestionResponse.model_validate(job)


@router.get("/status/{job_id}", response_model=IngestionResponse)
async def get_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    jid = uuid.UUID(job_id)
    job = await db.get(IngestionJob, jid)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return IngestionResponse.model_validate(job)


@router.get("/jobs", response_model=list[IngestionResponse])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IngestionJob).order_by(IngestionJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [IngestionResponse.model_validate(j) for j in jobs]
