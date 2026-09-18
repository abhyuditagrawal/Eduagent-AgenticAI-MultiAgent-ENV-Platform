"""Bayesian Knowledge Tracing + predictive forgetting endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.knowledge_tracing import (
    get_mastery_probabilities,
    get_forgetting_forecast,
    apply_bkt_observation,
    fit_student_bkt_params,
    get_effective_bkt_params,
    predict_learning_outcome,
)

router = APIRouter(prefix="/api/knowledge-tracing", tags=["knowledge-tracing"])


@router.get("/mastery")
async def mastery_probabilities(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-concept BKT mastery probability, current recall, and forecast."""
    return await get_mastery_probabilities(
        db, current_user.id, uuid.UUID(subject_id)
    )


@router.get("/forgetting-forecast")
async def forgetting_forecast(
    subject_id: str = Query(...),
    horizon_days: int = Query(14, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Timeline of concepts predicted to be forgotten within the horizon."""
    return await get_forgetting_forecast(
        db, current_user.id, uuid.UUID(subject_id), horizon_days=horizon_days
    )


@router.post("/observe")
async def observe(
    concept_id: str = Query(...),
    correct: bool = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a single correct/incorrect observation and update BKT."""
    result = await apply_bkt_observation(
        db, current_user.id, uuid.UUID(concept_id), correct
    )
    return result or {"error": "concept not tracked for this student"}


@router.post("/fit-params")
async def fit_params(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Re)fit this student's personalised BKT parameters via EM.

    A no-op (returns fitted=false) until enough raw observations exist -
    see MIN_OBSERVATIONS_FOR_FITTING in the service.
    """
    return await fit_student_bkt_params(db, current_user.id)


@router.get("/params")
async def bkt_params(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The BKT parameters currently in effect for this student (personalised or global)."""
    return await get_effective_bkt_params(db, current_user.id)


@router.get("/outcome-prediction")
async def outcome_prediction(
    subject_id: str = Query(...),
    exam_date: str | None = Query(None, description="ISO date/datetime; defaults to 14 days out"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Forecast likely assessment performance on a future date from BKT mastery
    trajectories and forgetting-curve projections (Future Work item #2)."""
    parsed_date = datetime.fromisoformat(exam_date) if exam_date else None
    return await predict_learning_outcome(
        db, current_user.id, uuid.UUID(subject_id), exam_date=parsed_date
    )
