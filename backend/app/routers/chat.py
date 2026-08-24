import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chat import Conversation, Message
from app.models.subject import Subject
from app.models.student import Enrollment
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    ConversationResponse,
)
from app.agents.orchestrator import get_orchestrator
from app.services.streaming import stream_agent_response
from app.services.student_state import (
    get_student_state,
    update_concept_confidence,
    get_prerequisite_gaps,
)
from app.services.conversation_context import (
    get_agent_context,
    update_agent_context,
    get_active_mode,
)
from app.services.learning_genome import get_genome_summary
from app.services.agent_analytics import log_agent_invocation, log_learning_event

logger = structlog.get_logger()

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _resolve_subject(
    db: AsyncSession,
    requested_subject_id,
    conversation: Conversation,
    student_id,
) -> tuple[object | None, str | None, str | None]:
    """Work out which subject this turn belongs to, and remember it.

    Retrieval is scoped by subject code: with no subject resolved the agents
    never search the uploaded course material and answer from general knowledge
    instead, which reads as "it cannot see my syllabus". So an explicit choice is
    persisted onto the conversation, and an unspecified one falls back to the
    student's enrolments rather than giving up.
    """
    subject_id = requested_subject_id or conversation.subject_id

    if subject_id is None:
        result = await db.execute(
            select(Subject)
            .join(Enrollment, Enrollment.subject_id == Subject.id)
            .where(Enrollment.student_id == student_id)
            .order_by(Subject.code)
        )
        enrolled = result.scalars().all()
        if enrolled:
            # Deterministic pick: grounded in the wrong subject is still
            # recoverable (the trace panel shows the sources), ungrounded is not.
            subject_id = enrolled[0].id
            if len(enrolled) > 1:
                logger.info(
                    "subject_defaulted_from_enrolment",
                    student_id=str(student_id),
                    subject=enrolled[0].code,
                    enrolled_count=len(enrolled),
                )

    if subject_id is None:
        return None, None, None

    subject = await db.get(Subject, subject_id)
    if not subject:
        return None, None, None

    # Persist a switch so later turns in this conversation stay on this subject.
    if conversation.subject_id != subject.id:
        conversation.subject_id = subject.id
        await db.commit()

    return subject.id, subject.code, subject.name


@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Get or create conversation
    conversation = None
    if data.conversation_id:
        conversation = await db.get(Conversation, data.conversation_id)
        if not conversation or conversation.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    if conversation is None:
        conversation = Conversation(
            student_id=current_user.id,
            subject_id=data.subject_id,
            title=data.message[:100],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # 2. Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.commit()

    # 3. Determine subject
    subject_id, subject_code, subject_name = await _resolve_subject(
        db, data.subject_id, conversation, current_user.id
    )

    # 4. Load conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    history_msgs = history_result.scalars().all()
    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in history_msgs[-10:]
    ]

    # 5. Load student state
    student_state = {}
    if subject_id:
        student_state = await get_student_state(db, current_user.id, subject_id)

    # 6. Build initial AgentState
    initial_state = {
        "messages": [{"role": "user", "content": data.message}],
        "student_id": str(current_user.id),
        "subject_id": str(subject_id) if subject_id else None,
        "subject_code": subject_code,
        "subject_name": subject_name,
        "student_state": student_state,
        "intent": data.agent_override,
        "active_agent": None,
        "rag_context": [],
        "concept_ids_touched": [],
        "concept_updates": [],
        "metadata": {},
        "response": "",
        "conversation_history": conversation_history,
    }

    # 7. Run orchestrator
    try:
        orchestrator = get_orchestrator()
        final_state = await orchestrator.ainvoke(initial_state)
    except Exception as e:
        logger.error("orchestrator_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process request: {str(e)}",
        )

    # 8. Apply concept updates
    for update in final_state.get("concept_updates", []):
        try:
            await update_concept_confidence(
                db,
                current_user.id,
                uuid.UUID(update["concept_id"]),
                update["quality"],
            )
        except Exception as e:
            logger.warning("concept_update_failed", error=str(e))

    # 9. Build metadata
    response_text = final_state.get("response", "")
    agent_type = final_state.get("active_agent", "unknown")
    metadata = final_state.get("metadata", {})

    # Add RAG source info
    rag_context = final_state.get("rag_context", [])
    if rag_context:
        metadata["rag_sources"] = [
            {
                "source_file": c.get("source_file", ""),
                "page": c.get("page", 0),
                "score": c.get("score", 0),
            }
            for c in rag_context
        ]

    # Add touched concepts names
    touched_ids = final_state.get("concept_ids_touched", [])
    if touched_ids and student_state:
        metadata["concepts_touched"] = [
            student_state[cid]["concept_name"]
            for cid in touched_ids
            if cid in student_state
        ]

    metadata["confidence_updates"] = final_state.get("concept_updates", [])

    # 10. Save assistant message
    conversation.agent_type = agent_type
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        agent_type=agent_type,
        metadata_=metadata,
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(
        response=response_text,
        conversation_id=conversation.id,
        agent_type=agent_type,
        metadata=metadata,
    )


@router.post("/stream")
async def chat_stream(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Get or create conversation
    conversation = None
    if data.conversation_id:
        conversation = await db.get(Conversation, data.conversation_id)
        if not conversation or conversation.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    if conversation is None:
        conversation = Conversation(
            student_id=current_user.id,
            subject_id=data.subject_id,
            title=data.message[:100],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # 2. Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.commit()

    # 3. Determine subject
    subject_id, subject_code, subject_name = await _resolve_subject(
        db, data.subject_id, conversation, current_user.id
    )

    # 4. History
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    history_msgs = history_result.scalars().all()
    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in history_msgs[-10:]
    ]

    # 5. Student state
    student_state = {}
    if subject_id:
        student_state = await get_student_state(db, current_user.id, subject_id)

    # 6. Load conversation agent context (for multi-turn protege/viva)
    agent_context = await get_agent_context(db, conversation.id)
    active_mode = await get_active_mode(db, conversation.id)

    # 7. Build state
    metadata = {}
    if agent_context:
        metadata["agent_context"] = agent_context
    if active_mode:
        metadata["active_mode"] = active_mode

    # Learning Genome: inject the student's cognitive fingerprint for personalisation
    try:
        genome_summary = await get_genome_summary(db, current_user.id)
        if genome_summary:
            metadata["genome_summary"] = genome_summary
    except Exception:
        pass

    initial_state = {
        "messages": [{"role": "user", "content": data.message}],
        "student_id": str(current_user.id),
        "subject_id": str(subject_id) if subject_id else None,
        "subject_code": subject_code,
        "subject_name": subject_name,
        "student_state": student_state,
        "intent": data.agent_override,
        "active_agent": None,
        "rag_context": [],
        "concept_ids_touched": [],
        "concept_updates": [],
        "metadata": metadata,
        "response": "",
        "conversation_history": conversation_history,
        "_conversation_id": str(conversation.id),
        "_message_id": "",
    }

    async def event_generator():
        full_response = ""
        agent_type = "unknown"
        all_metadata: dict = {}
        done_data: dict = {}
        stream_error: str | None = None

        try:
            async for event_type, event_data in stream_agent_response(initial_state):
                if event_type == "token":
                    full_response += event_data.get("content", "")
                elif event_type == "agent_start":
                    agent_type = event_data.get("agent", "unknown")
                    all_metadata["intent"] = event_data.get("intent", "")
                    all_metadata["agent_type"] = agent_type
                elif event_type == "rag_results":
                    all_metadata["rag_sources"] = event_data.get("sources", [])
                elif event_type == "concept_update":
                    all_metadata.setdefault("confidence_updates", []).append(event_data)
                elif event_type == "concepts_touched":
                    all_metadata["concepts_touched"] = event_data.get("concepts", [])
                elif event_type == "error":
                    stream_error = event_data.get("message", "unknown error")
                elif event_type == "done":
                    event_data["conversation_id"] = str(conversation.id)
                    done_data = event_data

                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

            # Save assistant message after streaming completes
            msg_metadata = all_metadata.copy()
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response,
                agent_type=agent_type,
                metadata_=msg_metadata,
            )
            db.add(assistant_msg)
            conversation.agent_type = agent_type
            await db.commit()
            await db.refresh(assistant_msg)

            # Apply concept updates
            for update in all_metadata.get("confidence_updates", []):
                try:
                    await update_concept_confidence(
                        db,
                        current_user.id,
                        uuid.UUID(update["concept_id"]),
                        update["quality"],
                    )
                except Exception:
                    pass

            # Record the real invocation so agent analytics and the learning path
            # are built from actual usage.
            try:
                await log_agent_invocation(
                    db,
                    student_id=current_user.id,
                    conversation_id=conversation.id,
                    agent_type=agent_type,
                    intent=all_metadata.get("intent") or "general",
                    response_time_ms=done_data.get("response_time_ms", 0),
                    rag_chunks_used=done_data.get("rag_chunks_used", 0),
                    success=stream_error is None,
                    error_message=stream_error,
                )
                await log_learning_event(
                    db,
                    student_id=current_user.id,
                    event_type="agent_interaction",
                    subject_id=subject_id,
                    agent_type=agent_type,
                    data={
                        "intent": all_metadata.get("intent") or "general",
                        "concepts_touched": all_metadata.get("concepts_touched", []),
                        "rag_chunks_used": done_data.get("rag_chunks_used", 0),
                        "question": data.message[:200],
                    },
                )
                for update in all_metadata.get("confidence_updates", []):
                    await log_learning_event(
                        db,
                        student_id=current_user.id,
                        event_type="concept_assessed",
                        concept_id=uuid.UUID(update["concept_id"]),
                        subject_id=subject_id,
                        agent_type=agent_type,
                        data={"quality": update.get("quality")},
                    )
                await db.commit()
            except Exception as e:
                logger.warning("analytics_logging_failed", error=str(e))

            # Update conversation agent context for multi-turn modes
            if agent_type in ("protege", "viva"):
                ctx = agent_context.copy() if agent_context else {}
                ctx["active_mode"] = {
                    "protege": "teach_me",
                    "viva": "viva",
                }.get(agent_type, agent_type)
                # Increment exchange count
                ctx["exchange_count"] = ctx.get("exchange_count", 0) + 1
                await update_agent_context(db, conversation.id, ctx)

        except Exception as e:
            logger.error("stream_error", error=str(e))
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


@router.get("/history", response_model=list[ConversationResponse])
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Conversation)
        .where(Conversation.student_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    conversations = result.scalars().all()
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=list[MessageResponse])
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = uuid.UUID(conversation_id)
    conversation = await db.get(Conversation, cid)
    if not conversation or conversation.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == cid)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            agent_type=m.agent_type,
            metadata=m.metadata_ or {},
            created_at=m.created_at,
        )
        for m in messages
    ]
