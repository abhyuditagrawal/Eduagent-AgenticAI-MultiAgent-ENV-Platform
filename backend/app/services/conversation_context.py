import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Conversation

logger = structlog.get_logger()


async def get_agent_context(db: AsyncSession, conversation_id) -> dict:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        return {}

    metadata = conversation.metadata_ or {} if hasattr(conversation, "metadata_") else {}
    return metadata.get("agent_context", {})


async def update_agent_context(db: AsyncSession, conversation_id, context: dict):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        return

    if not hasattr(conversation, "metadata_") or conversation.metadata_ is None:
        conversation.metadata_ = {}

    current = dict(conversation.metadata_)
    current["agent_context"] = context

    # Also store active_mode for routing
    active_mode = context.get("active_mode")
    if active_mode:
        current["active_mode"] = active_mode

    conversation.metadata_ = current
    await db.commit()


async def get_active_mode(db: AsyncSession, conversation_id) -> str | None:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        return None

    metadata = conversation.metadata_ or {} if hasattr(conversation, "metadata_") else {}
    return metadata.get("active_mode")


async def clear_active_mode(db: AsyncSession, conversation_id):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        return

    if hasattr(conversation, "metadata_") and conversation.metadata_:
        current = dict(conversation.metadata_)
        current.pop("active_mode", None)
        current.pop("agent_context", None)
        conversation.metadata_ = current
        await db.commit()
