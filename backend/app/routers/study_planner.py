"""Study planner endpoints: generate and retrieve AI-powered study plans."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.study_planner import generate_study_plan, get_study_plans

router = APIRouter(prefix="/api/study-planner", tags=["study-planner"])


class PlanRequest(BaseModel):
    subject_id: str
    exam_date: str | None = None
    study_hours_per_day: float = 2.0


@router.post("/generate")
async def create_plan(
    req: PlanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exam_dt = None
    if req.exam_date:
        try:
            exam_dt = datetime.fromisoformat(req.exam_date)
        except ValueError:
            raise HTTPException(400, "Invalid exam_date format. Use ISO format.")

    return await generate_study_plan(
        db, user.id, req.subject_id,
        exam_date=exam_dt,
        study_hours_per_day=req.study_hours_per_day,
    )


@router.get("")
async def list_plans(
    subject_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_study_plans(db, user.id, subject_id=subject_id)
