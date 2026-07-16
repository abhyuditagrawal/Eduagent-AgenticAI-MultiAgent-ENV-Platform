"""Bayesian Knowledge Tracing + predictive forgetting endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.knowledge_tracing import (
    get_mastery_probabilities,
    get_forgetting_forecast,
    apply_bkt_observation,
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
