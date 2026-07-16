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

logger = structlog.get_logger()


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

            job.status = "completed"
            job.chunks = len(chunks)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info("ingestion_complete", job_id=str(job_id), chunks=len(chunks))

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
