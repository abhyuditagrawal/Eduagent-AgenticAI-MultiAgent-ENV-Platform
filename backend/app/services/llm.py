import time
from typing import AsyncGenerator

import structlog
import google.generativeai as genai

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

_model = None


def get_gemini_model():
    global _model
    if _model is None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-2.0-flash")
    return _model


def _build_prompt(
    user_message: str,
    system_prompt: str | None = None,
    context_chunks: list[dict] | None = None,
    conversation_history: list[dict] | None = None,
) -> str:
    if system_prompt is None:
        system_prompt = (
            "You are EduAgent, a helpful AI educational assistant. "
            "Answer the student's question using the provided context from their course material. "
            "If the context doesn't contain relevant information, say so honestly. "
            "Be clear, concise, and educational in your responses."
        )

    context_text = ""
    if context_chunks:
        context_text = "\n\n--- Retrieved Context ---\n"
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk.get("source_file", "unknown")
            page = chunk.get("page", "?")
            context_text += f"\n[Source {i}: {source}, Page {page}]\n{chunk['text']}\n"
        context_text += "\n--- End Context ---\n"

    history_text = ""
    if conversation_history:
        history_text = "\n\n--- Conversation History ---\n"
        for msg in conversation_history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_text += f"{role}: {content}\n"
        history_text += "--- End History ---\n"

    return f"{system_prompt}\n{context_text}\n{history_text}\nStudent: {user_message}"


async def generate_response(
    user_message: str,
    context_chunks: list[dict] | None = None,
    conversation_history: list[dict] | None = None,
    system_prompt: str | None = None,
) -> str:
    model = get_gemini_model()
    full_prompt = _build_prompt(user_message, system_prompt, context_chunks, conversation_history)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            return response.text
        except Exception as e:
            logger.warning("gemini_api_error", attempt=attempt, error=str(e))
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"Failed to get response from Gemini after {max_retries} retries: {e}")


async def generate_response_stream(
    user_message: str,
    context_chunks: list[dict] | None = None,
    conversation_history: list[dict] | None = None,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    model = get_gemini_model()
    full_prompt = _build_prompt(user_message, system_prompt, context_chunks, conversation_history)

    try:
        response = model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        logger.error("gemini_stream_error", error=str(e))
        raise RuntimeError(f"Streaming failed: {e}")
