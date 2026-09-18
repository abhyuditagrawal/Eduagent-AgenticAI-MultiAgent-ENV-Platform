from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine

settings = get_settings()
logger = structlog.get_logger()


# Arbitrary constant identifying the migration lock across workers.
MIGRATION_LOCK_ID = 727_314_001


async def run_migrations():
    import subprocess
    import os

    alembic_ini = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    if not os.path.exists(alembic_ini):
        logger.warning("alembic_ini_not_found", path=alembic_ini)
        return

    # Every uvicorn worker runs this lifespan, so without a lock they race each
    # other and all but one fail. Serialise them on a Postgres advisory lock:
    # the winner migrates, the rest find the schema already at head.
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID}
        )
        try:
            subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=os.path.dirname(alembic_ini),
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("migrations_applied")
        except subprocess.CalledProcessError as e:
            logger.error("migration_failed", error=e.stderr)
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(
        "starting_eduagent_backend",
        version="0.1.0",
        database=settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "unknown",
        qdrant=f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
    )

    # Check DB connection
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database_connected")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))

    # Run migrations
    await run_migrations()

    # Check Qdrant connection
    try:
        from app.rag.vector_store import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        logger.info("qdrant_connected")
    except Exception as e:
        logger.warning("qdrant_connection_failed", error=str(e))

    # Verify Gemini API key
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        model.count_tokens("test")
        logger.info("gemini_api_key_valid", model=settings.GEMINI_MODEL)
    except Exception as e:
        logger.warning("gemini_api_key_check_failed", error=str(e))

    # Check Redis connection
    try:
        from app.services.cache import get_redis
        redis_client = await get_redis()
        if redis_client:
            await redis_client.ping()
            logger.info("redis_connected")
        else:
            logger.warning("redis_not_available")
    except Exception as e:
        logger.warning("redis_connection_failed", error=str(e))

    # Pre-warm the local embedding model. It's lazily loaded on first use by
    # design (see rag/embeddings.py), but leaving that first load to happen
    # inside a student's first chat request risks that request timing out
    # waiting on model weights instead of an actual answer - loading it here
    # means the cost is paid once at boot, not on someone's first question.
    try:
        from app.rag.embeddings import embed_query
        embed_query("warmup")
        logger.info("embedding_model_warmed")
    except Exception as e:
        logger.warning("embedding_model_warmup_failed", error=str(e))

    logger.info("startup_complete")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("eduagent_backend_shutdown")


app = FastAPI(
    title="EduAgent API",
    description="Multi-Agent AI Educational Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.NEXTAUTH_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.routers import (
    auth, subjects, chat, ingestion, concepts, nudges, dashboard,
    flashcards, analytics, study_planner, progress_report,
    custom_agents, study_rooms, image_chat, ws_study,
    knowledge_tracing, debate, learning_genome, knowledge_frontier,
    annotations,
)

app.include_router(auth.router)
app.include_router(subjects.router)
app.include_router(chat.router)
app.include_router(ingestion.router)
app.include_router(concepts.router)
app.include_router(nudges.router)
app.include_router(dashboard.router)
app.include_router(flashcards.router)
app.include_router(analytics.router)
app.include_router(study_planner.router)
app.include_router(progress_report.router)
app.include_router(custom_agents.router)
app.include_router(study_rooms.router)
app.include_router(image_chat.router)
app.include_router(ws_study.router)
app.include_router(knowledge_tracing.router)
app.include_router(debate.router)
app.include_router(learning_genome.router)
app.include_router(knowledge_frontier.router)
app.include_router(annotations.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "eduagent-backend"}
