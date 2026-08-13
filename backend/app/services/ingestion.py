import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.ingestion import IngestionJob
from app.models.subject import Subject
from app.rag.chunker import extract_text_from_pdf, chunk_text
from app.rag.embeddings import embed_texts
from app.rag.vector_store import ensure_collection, upsert_chunks
from app.services.concept_graph import (
    extract_concepts_from_syllabus,
    auto_detect_dependencies,
)
from app.services.student_state import sync_student_concepts

logger = structlog.get_logger()

# How much of the document to feed the concept extractor, and how widely to sample it.
CONCEPT_SOURCE_CHAR_BUDGET = 24000
CONCEPT_SOURCE_MAX_PAGES = 40


def _build_concept_source_text(pages: list[dict]) -> str:
    """Sample text evenly across the whole document.

    Reading only the first few pages would miss everything past the introduction,
    so pages are sampled at a stride and truncated to a character budget.
    """
    if not pages:
        return ""

    if len(pages) <= CONCEPT_SOURCE_MAX_PAGES:
        selected = pages
    else:
        stride = len(pages) / CONCEPT_SOURCE_MAX_PAGES
        selected = [pages[int(i * stride)] for i in range(CONCEPT_SOURCE_MAX_PAGES)]

    per_page_budget = max(400, CONCEPT_SOURCE_CHAR_BUDGET // max(1, len(selected)))
    parts = []
    used = 0
    for page in selected:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        snippet = text[:per_page_budget]
        if used + len(snippet) > CONCEPT_SOURCE_CHAR_BUDGET:
            snippet = snippet[: CONCEPT_SOURCE_CHAR_BUDGET - used]
        if not snippet:
            break
        parts.append(f"[Page {page.get('page', '?')}]\n{snippet}")
        used += len(snippet)
        if used >= CONCEPT_SOURCE_CHAR_BUDGET:
            break

    return "\n\n".join(parts)


async def process_pdf(job_id: uuid.UUID, subject_id: uuid.UUID, file_path: str, filename: str):
    async with async_session() as db:
        try:
            job = await db.get(IngestionJob, job_id)
            if not job:
                logger.error("ingestion_job_not_found", job_id=str(job_id))
                return

            job.status = "processing"
            await db.commit()

            result = await db.execute(select(Subject).where(Subject.id == subject_id))
            subject = result.scalar_one_or_none()
            if not subject:
                job.status = "failed"
                job.error = "Subject not found"
                await db.commit()
                return

            logger.info("ingestion_start", job_id=str(job_id), filename=filename)

            pages = extract_text_from_pdf(file_path)
            logger.info("pdf_extracted", pages=len(pages))

            chunks = chunk_text(pages, chunk_size=500, overlap=50)
            logger.info("text_chunked", chunks=len(chunks))

            for chunk in chunks:
                chunk["source_file"] = filename

            texts = [c["text"] for c in chunks]
            embeddings = embed_texts(texts)
            logger.info("embeddings_generated", count=len(embeddings))

            collection_name = f"subject_{subject.code.lower()}"
            ensure_collection(collection_name)
            upsert_chunks(collection_name, chunks, embeddings)
            logger.info("chunks_upserted", collection=collection_name)

            # Build the concept graph from what was actually uploaded, so mastery
            # tracking, the ZPD view and the dashboards have real concepts to track.
            concepts_created = 0
            try:
                source_text = _build_concept_source_text(pages)
                if source_text:
                    extracted = await extract_concepts_from_syllabus(
                        db, subject_id, source_text
                    )
                    concepts_created = len(extracted)
                    logger.info("concepts_extracted_from_pdf", count=concepts_created)

                    edges = await auto_detect_dependencies(
                        db, subject_id, [c["text"] for c in chunks]
                    )
                    logger.info("dependencies_detected", count=len(edges))

                    await sync_student_concepts(db, subject_id)
            except Exception as e:
                # Concept extraction is best-effort — the vector store is already
                # populated, so the RAG agents still work without it.
                logger.warning("concept_generation_failed", job_id=str(job_id), error=str(e))

            job = await db.get(IngestionJob, job_id)
            job.status = "completed"
            job.chunks = len(chunks)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "ingestion_complete",
                job_id=str(job_id),
                chunks=len(chunks),
                concepts_created=concepts_created,
            )

        except Exception as e:
            logger.error("ingestion_failed", job_id=str(job_id), error=str(e))
            try:
                job = await db.get(IngestionJob, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    await db.commit()
            except Exception:
                pass
