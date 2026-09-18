"""WebSocket endpoint for live study group collaboration."""

import json
import uuid
from datetime import datetime, timezone
from collections import defaultdict

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from jose import jwt, JWTError

from app.config import get_settings
from app.services.llm import get_gemini_model
from app.agents.debate import judge_peer_debate
import google.generativeai as genai

settings = get_settings()
logger = structlog.get_logger()
router = APIRouter(tags=["study-rooms-ws"])

# In-memory room connections (per-process; fine for single-server)
room_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
room_history: dict[str, list[dict]] = defaultdict(list)

# Collaborative whiteboard (Future Work item #3): ephemeral per-room stroke
# log, replayed to anyone who joins mid-session. No persistence - a
# whiteboard is a live scratch space for the session, not course material.
room_whiteboard: dict[str, list[dict]] = defaultdict(list)
MAX_WHITEBOARD_STROKES = 500

# Peer-debate mode (Future Work item #8): two-or-more students argue a
# question, AI moderates. Ephemeral per-room, reset whenever a new topic starts.
room_debate: dict[str, dict] = {}

MAX_HISTORY = 50


def _verify_ws_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        # Match the HTTP dependency: a refresh token must not authenticate a
        # session, or it becomes a 7-day credential instead of a 30-minute one.
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def _broadcast(room_id: str, message: dict, exclude_user: str | None = None):
    dead = []
    for user_id, ws in room_connections[room_id].items():
        if user_id == exclude_user:
            continue
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(user_id)
    for uid in dead:
        room_connections[room_id].pop(uid, None)


@router.websocket("/ws/study-room/{room_id}")
async def study_room_ws(websocket: WebSocket, room_id: str):
    # Authenticate via query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user_data = _verify_ws_token(token)
    if not user_data:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = user_data.get("sub", "unknown")
    user_email = user_data.get("email", "unknown")

    await websocket.accept()
    room_connections[room_id][user_id] = websocket

    # Send history
    if room_history[room_id]:
        await websocket.send_json({
            "type": "history",
            "messages": room_history[room_id][-MAX_HISTORY:],
        })

    # Replay the whiteboard so a mid-session joiner sees the current drawing
    if room_whiteboard[room_id]:
        await websocket.send_json({
            "type": "whiteboard_history",
            "strokes": room_whiteboard[room_id],
        })

    # Replay an in-progress peer debate, if any
    if room_id in room_debate:
        await websocket.send_json({
            "type": "debate_state",
            "debate": room_debate[room_id],
        })

    # Announce join
    await _broadcast(room_id, {
        "type": "system",
        "content": f"{user_email} joined the room",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    logger.info("ws_user_joined", room_id=room_id, user_id=user_id)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "message")

            if msg_type == "message":
                broadcast_msg = {
                    "type": "message",
                    "user_id": user_id,
                    "user_email": user_email,
                    "content": msg.get("content", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                room_history[room_id].append(broadcast_msg)
                if len(room_history[room_id]) > MAX_HISTORY:
                    room_history[room_id] = room_history[room_id][-MAX_HISTORY:]

                await _broadcast(room_id, broadcast_msg)

            elif msg_type == "ai_question":
                # Someone asks the AI a question in the group
                question = msg.get("content", "")
                subject_context = msg.get("subject", "")

                # Broadcast the question
                q_msg = {
                    "type": "message",
                    "user_id": user_id,
                    "user_email": user_email,
                    "content": f"[AI Question] {question}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                room_history[room_id].append(q_msg)
                await _broadcast(room_id, q_msg)

                # Generate AI response
                try:
                    model = get_gemini_model()
                    prompt = (
                        f"You are EduAgent, helping a study group. "
                        f"Subject: {subject_context}\n"
                        f"A student asks: {question}\n"
                        f"Give a clear, educational answer."
                    )
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.GenerationConfig(
                            temperature=0.7, max_output_tokens=2048
                        ),
                    )
                    ai_msg = {
                        "type": "ai_response",
                        "content": response.text,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                except Exception as e:
                    ai_msg = {
                        "type": "ai_response",
                        "content": f"Sorry, I couldn't generate a response: {str(e)}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                room_history[room_id].append(ai_msg)
                await _broadcast(room_id, ai_msg)

            elif msg_type == "whiteboard_draw":
                # A single stroke (freehand line, shape, or eraser pass).
                # Broadcast-only to everyone else; the sender already has it locally.
                stroke = {
                    "user_id": user_id,
                    "stroke": msg.get("stroke", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                room_whiteboard[room_id].append(stroke)
                if len(room_whiteboard[room_id]) > MAX_WHITEBOARD_STROKES:
                    room_whiteboard[room_id] = room_whiteboard[room_id][-MAX_WHITEBOARD_STROKES:]
                await _broadcast(room_id, {"type": "whiteboard_draw", **stroke}, exclude_user=user_id)

            elif msg_type == "whiteboard_clear":
                room_whiteboard[room_id] = []
                await _broadcast(room_id, {
                    "type": "whiteboard_clear",
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif msg_type == "annotation":
                # Live broadcast for a REST-persisted annotation (see
                # routers/annotations.py) so everyone in the room sees it
                # appear immediately, without polling.
                payload = {
                    "type": "annotation",
                    "user_id": user_id,
                    "user_email": user_email,
                    "annotation": msg.get("annotation", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await _broadcast(room_id, payload, exclude_user=user_id)

            elif msg_type == "debate_start":
                # Reset/start a peer debate on a new topic.
                room_debate[room_id] = {
                    "topic": msg.get("topic", ""),
                    "subject_code": msg.get("subject_code"),
                    "subject_name": msg.get("subject_name"),
                    "arguments": {},
                    "verdict": None,
                    "started_by": user_id,
                }
                await _broadcast(room_id, {
                    "type": "debate_state",
                    "debate": room_debate[room_id],
                })

            elif msg_type == "debate_argument":
                if room_id not in room_debate:
                    continue
                room_debate[room_id]["arguments"][user_id] = {
                    "name": user_email,
                    "content": msg.get("content", ""),
                }
                await _broadcast(room_id, {
                    "type": "debate_state",
                    "debate": room_debate[room_id],
                })

            elif msg_type == "debate_judge":
                debate_state = room_debate.get(room_id)
                if not debate_state or not debate_state["arguments"]:
                    continue
                try:
                    verdict = await judge_peer_debate(
                        topic=debate_state["topic"],
                        arguments=list(debate_state["arguments"].values()),
                        subject_code=debate_state.get("subject_code"),
                        subject_name=debate_state.get("subject_name"),
                    )
                except Exception as e:
                    logger.error("peer_debate_judge_failed", room_id=room_id, error=str(e))
                    verdict = f"The moderator couldn't reach the AI judge just now: {e}"
                debate_state["verdict"] = verdict
                await _broadcast(room_id, {
                    "type": "debate_verdict",
                    "verdict": verdict,
                    "debate": debate_state,
                })

    except WebSocketDisconnect:
        room_connections[room_id].pop(user_id, None)
        await _broadcast(room_id, {
            "type": "system",
            "content": f"{user_email} left the room",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("ws_user_left", room_id=room_id, user_id=user_id)

        # Clean up empty rooms
        if not room_connections[room_id]:
            del room_connections[room_id]
            room_history.pop(room_id, None)
            room_whiteboard.pop(room_id, None)
            room_debate.pop(room_id, None)
    except Exception as e:
        logger.error("ws_error", room_id=room_id, error=str(e))
        room_connections[room_id].pop(user_id, None)
