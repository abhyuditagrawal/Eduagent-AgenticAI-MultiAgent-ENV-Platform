"""Analytics endpoints: agent performance, class-level stats, learning path."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.services.agent_analytics import (
    get_agent_analytics,
    get_class_analytics,
    get_learning_path,
)
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/agents")
async def agent_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Agent performance analytics (admin only)."""
    cached = await cache_get("analytics", "agents", str(days))
    if cached:
        return cached

    data = await get_agent_analytics(db, days=days)
    await cache_set("analytics", "agents", str(days), value=data, ttl=300)
    return data


@router.get("/class")
async def class_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Class-level aggregated analytics (admin only)."""
    cached = await cache_get("analytics", "class")
    if cached:
        return cached

    data = await get_class_analytics(db)
    await cache_set("analytics", "class", value=data, ttl=300)
    return data


@router.get("/learning-path")
async def learning_path(
    subject_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a student's learning path timeline."""
    return await get_learning_path(db, user.id, subject_id=subject_id)
