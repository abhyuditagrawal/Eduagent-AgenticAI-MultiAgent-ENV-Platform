"""Knowledge Frontier / ZPD endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.knowledge_frontier import compute_frontier

router = APIRouter(prefix="/api/frontier", tags=["knowledge-frontier"])


@router.get("")
async def knowledge_frontier(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partition the concept graph into mastered / frontier (ZPD) / locked."""
    return await compute_frontier(db, current_user.id, uuid.UUID(subject_id))
