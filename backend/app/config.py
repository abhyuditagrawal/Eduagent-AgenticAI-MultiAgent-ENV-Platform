from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = "eduagent"
    POSTGRES_PASSWORD: str = "eduagent_dev"
    POSTGRES_DB: str = "eduagent"
    DATABASE_URL: str = "postgresql+asyncpg://eduagent:eduagent_dev@localhost:5432/eduagent"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    GEMINI_API_KEY: str = "your-gemini-api-key-here"
    # Configurable so a retired model can be swapped via .env without a rebuild.
    # The "-latest" alias tracks the current model instead of pinning to one that
    # Google will eventually turn off. Flash-Lite is the default because a single
    # chat turn costs 3-4 API calls and the full Flash tier allows only 5 requests
    # per minute on the free plan, which rate-limits an ordinary conversation.
    GEMINI_MODEL: str = "gemini-flash-lite-latest"

    # Frontend
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    NEXTAUTH_SECRET: str = "change-me-in-production"
    NEXTAUTH_URL: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
