"""Multi-Agent Debate & Consensus endpoint (SSE streaming)."""

import json
import uuid

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.subject import Subject
from app.models.user import User
from app.agents.debate import run_debate_stream

logger = structlog.get_logger()

router = APIRouter(prefix="/api/debate", tags=["debate"])


class DebateRequest(BaseModel):
    question: str
    subject_id: str | None = None
    rounds: int = 1


@router.post("/stream")
async def debate_stream(
    data: DebateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject_code = None
    subject_name = None
    if data.subject_id:
        subject = await db.get(Subject, uuid.UUID(data.subject_id))
        if subject:
            subject_code = subject.code
            subject_name = subject.name

    async def event_generator():
        try:
            async for event_type, event_data in run_debate_stream(
                question=data.question,
                subject_code=subject_code,
                subject_name=subject_name,
                rounds=max(1, min(3, data.rounds)),
            ):
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            logger.error("debate_stream_error", error=str(e))
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
