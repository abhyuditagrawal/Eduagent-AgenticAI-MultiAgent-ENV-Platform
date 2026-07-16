"""Image/diagram understanding endpoint using Gemini multimodal."""

import base64
import io

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import google.generativeai as genai

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.llm import get_gemini_model
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/image-chat", tags=["image-chat"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@router.post("")
async def analyze_image(
    file: UploadFile = File(...),
    question: str = Form("Explain this diagram or image in detail."),
    subject_context: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload an image (diagram, flowchart, handwritten notes) and ask questions about it."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported image type: {file.content_type}. Use JPEG, PNG, GIF, or WebP.")

    image_data = await file.read()
    if len(image_data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image too large. Max 10MB.")

    # Configure Gemini for multimodal
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    system_context = ""
    if subject_context:
        system_context = f"\nThis is from the subject: {subject_context}. "

    prompt = (
        f"You are EduAgent, an AI educational assistant.{system_context}\n"
        f"A student has uploaded an image and asks: {question}\n\n"
        "Analyze the image carefully. If it's a diagram, explain each component. "
        "If it's handwritten notes, transcribe and clarify. "
        "If it's a flowchart, explain the logic flow. "
        "If there are errors in the diagram, point them out. "
        "Be educational, clear, and thorough."
    )

    try:
        image_part = {
            "mime_type": file.content_type,
            "data": image_data,
        }
        response = model.generate_content(
            [prompt, image_part],
            generation_config=genai.GenerationConfig(
                temperature=0.5, max_output_tokens=2048
            ),
        )
        return {
            "analysis": response.text,
            "filename": file.filename,
            "question": question,
        }
    except Exception as e:
        raise HTTPException(500, f"Image analysis failed: {str(e)}")
