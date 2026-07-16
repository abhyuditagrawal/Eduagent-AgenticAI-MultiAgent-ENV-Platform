"""Redis caching service for RAG queries and LLM responses."""

import json
import hashlib
from typing import Any

import structlog
import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

_redis_client = None

DEFAULT_TTL = 3600  # 1 hour


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            await _redis_client.ping()
            logger.info("redis_connected", url=settings.REDIS_URL)
        except Exception as e:
            logger.warning("redis_connection_failed", error=str(e))
            _redis_client = None
    return _redis_client


def _cache_key(prefix: str, *args: str) -> str:
    raw = ":".join(str(a) for a in args)
    hashed = hashlib.md5(raw.encode()).hexdigest()
    return f"eduagent:{prefix}:{hashed}"


async def cache_get(prefix: str, *args: str) -> Any | None:
    client = await get_redis()
    if client is None:
        return None
    try:
        key = _cache_key(prefix, *args)
        data = await client.get(key)
        if data:
            logger.debug("cache_hit", key=key)
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning("cache_get_error", error=str(e))
        return None


async def cache_set(prefix: str, *args: str, value: Any, ttl: int = DEFAULT_TTL):
    client = await get_redis()
    if client is None:
        return
    try:
        key = _cache_key(prefix, *args)
        await client.set(key, json.dumps(value, default=str), ex=ttl)
        logger.debug("cache_set", key=key, ttl=ttl)
    except Exception as e:
        logger.warning("cache_set_error", error=str(e))


async def cache_invalidate(prefix: str, *args: str):
    client = await get_redis()
    if client is None:
        return
    try:
        key = _cache_key(prefix, *args)
        await client.delete(key)
    except Exception as e:
        logger.warning("cache_invalidate_error", error=str(e))


async def cache_get_stats() -> dict:
    client = await get_redis()
    if client is None:
        return {"connected": False}
    try:
        info = await client.info("stats")
        return {
            "connected": True,
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "keys": await client.dbsize(),
        }
    except Exception:
        return {"connected": False}
