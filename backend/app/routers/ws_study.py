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
import google.generativeai as genai

settings = get_settings()
logger = structlog.get_logger()
router = APIRouter(tags=["study-rooms-ws"])

# In-memory room connections (per-process; fine for single-server)
room_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
room_history: dict[str, list[dict]] = defaultdict(list)

MAX_HISTORY = 50


def _verify_ws_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
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
    except Exception as e:
        logger.error("ws_error", room_id=room_id, error=str(e))
        room_connections[room_id].pop(user_id, None)
