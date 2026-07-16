from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select

from app.config import get_settings
from app.database import engine, async_session
from app.models.subject import Subject

settings = get_settings()
logger = structlog.get_logger()

SEED_SUBJECTS = [
    {"code": "MSA", "name": "Microservices Architecture", "description": "Design and implementation of microservices-based systems"},
    {"code": "HCI", "name": "Human-Computer Interaction", "description": "Principles of user interface design and usability"},
    {"code": "CS", "name": "Cyber Security", "description": "Information security, cryptography, and network defense"},
    {"code": "ML", "name": "Machine Learning", "description": "Supervised, unsupervised, and reinforcement learning algorithms"},
]


async def run_migrations():
    import subprocess
    import os

    alembic_ini = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    if os.path.exists(alembic_ini):
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
            logger.warning("migration_failed", error=e.stderr)
    else:
        logger.warning("alembic_ini_not_found", path=alembic_ini)


async def seed_subjects():
    async with async_session() as db:
        for subj_data in SEED_SUBJECTS:
            result = await db.execute(
                select(Subject).where(Subject.code == subj_data["code"])
            )
            if not result.scalar_one_or_none():
                subject = Subject(**subj_data)
                db.add(subject)
                logger.info("subject_seeded", code=subj_data["code"])
        await db.commit()


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

    # Seed subjects
    await seed_subjects()

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
        model = genai.GenerativeModel("gemini-2.0-flash")
        model.count_tokens("test")
        logger.info("gemini_api_key_valid")
    except Exception as e:
        logger.warning("gemini_api_key_check_failed", error=str(e))

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
from app.routers import auth, subjects, chat, ingestion, concepts, nudges, dashboard

app.include_router(auth.router)
app.include_router(subjects.router)
app.include_router(chat.router)
app.include_router(ingestion.router)
app.include_router(concepts.router)
app.include_router(nudges.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "eduagent-backend"}
