"""Learning Genome (cognitive fingerprint) endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.learning_genome import (
    compute_genome,
    get_genome,
    genome_to_dict,
)

router = APIRouter(prefix="/api/genome", tags=["learning-genome"])


@router.get("")
async def read_genome(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current learning genome, computing it if none exists."""
    genome = await get_genome(db, current_user.id)
    if genome is None:
        genome = await compute_genome(db, current_user.id)
    return genome_to_dict(genome)


@router.post("/refresh")
async def refresh_genome(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recompute the learning genome from the latest behavioural data."""
    genome = await compute_genome(db, current_user.id)
    return genome_to_dict(genome)
