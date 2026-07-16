"""Custom agent builder endpoints: CRUD for professor-defined agents."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.study import CustomAgent

router = APIRouter(prefix="/api/custom-agents", tags=["custom-agents"])


class AgentCreateRequest(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str
    rubric: dict = {}


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    rubric: dict | None = None
    is_active: bool | None = None


@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all active custom agents."""
    result = await db.execute(
        select(CustomAgent)
        .where(CustomAgent.is_active == True)
        .order_by(CustomAgent.created_at.desc())
    )
    agents = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "description": a.description,
            "system_prompt": a.system_prompt,
            "rubric": a.rubric,
            "agent_type": a.agent_type,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@router.post("", status_code=201)
async def create_agent(
    req: AgentCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Create a custom agent (admin only)."""
    agent = CustomAgent(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        rubric=req.rubric,
        created_by=user.id,
    )
    db.add(agent)
    await db.commit()
    return {
        "id": str(agent.id),
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "rubric": agent.rubric,
    }


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    req: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Update a custom agent (admin only)."""
    agent = await db.get(CustomAgent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    if req.name is not None:
        agent.name = req.name
    if req.description is not None:
        agent.description = req.description
    if req.system_prompt is not None:
        agent.system_prompt = req.system_prompt
    if req.rubric is not None:
        agent.rubric = req.rubric
    if req.is_active is not None:
        agent.is_active = req.is_active

    await db.commit()
    return {"id": str(agent.id), "name": agent.name, "updated": True}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Soft-delete a custom agent (admin only)."""
    agent = await db.get(CustomAgent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.is_active = False
    await db.commit()
    return {"deleted": True}
