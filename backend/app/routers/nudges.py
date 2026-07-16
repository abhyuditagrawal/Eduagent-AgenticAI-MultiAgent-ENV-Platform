from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.nudge_engine import generate_nudges
from app.services.student_state import decay_confidence

router = APIRouter(prefix="/api/nudges", tags=["nudges"])


@router.get("")
async def get_nudges(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Apply confidence decay before generating nudges
    await decay_confidence(db, current_user.id)
    nudges = await generate_nudges(db, current_user.id)
    return nudges
