"""Redis caching utility for API response caching.

Provides a connection pool, get/set helpers, pattern-based invalidation,
and a ``cached()`` decorator factory for FastAPI route handlers.
"""

import functools
import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.ConnectionPool | None = None


async def init_cache_pool() -> None:
    """Create the Redis connection pool.  Called from FastAPI lifespan."""
    global _pool
    _pool = aioredis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    logger.info("Redis cache pool initialised")


async def close_cache_pool() -> None:
    """Shut down the Redis connection pool."""
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None


def _client() -> aioredis.Redis:
    if _pool is None:
        raise RuntimeError("Cache pool not initialised — call init_cache_pool() first")
    return aioredis.Redis(connection_pool=_pool)


# ── Key helpers ──────────────────────────────────────────────────────

def cache_key(prefix: str, **params: Any) -> str:
    """Build a deterministic cache key from a prefix and keyword params.

    ``cache:sentiment:sectors:abc123def``
    """
    if not params:
        return f"cache:{prefix}"
    # Sort for determinism, stringify values
    raw = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"cache:{prefix}:{digest}"


# ── Get / Set / Invalidate ───────────────────────────────────────────

async def get_cached(key: str) -> Any | None:
    """Return deserialised value from Redis, or None on miss/error."""
    try:
        client = _client()
        raw = await client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception:
        logger.debug("cache get error for %s", key, exc_info=True)
    return None


async def set_cached(key: str, value: Any, ttl: int) -> None:
    """Serialise *value* to JSON and store with TTL seconds."""
    try:
        client = _client()
        await client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.debug("cache set error for %s", key, exc_info=True)


async def invalidate_pattern(pattern: str) -> int:
    """Delete all keys matching *pattern* via non-blocking SCAN."""
    deleted = 0
    try:
        client = _client()
        cursor: int | bytes = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                deleted += await client.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.debug("cache invalidate error for %s", pattern, exc_info=True)
    if deleted:
        logger.info("Cache invalidated %d keys matching %s", deleted, pattern)
    return deleted


# ── Serialisation helpers ────────────────────────────────────────────

def _to_serializable(result: Any) -> Any:
    """Convert Pydantic models (or lists thereof) to JSON-safe dicts."""
    if isinstance(result, list):
        return [_to_serializable(item) for item in result]
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result


# ── Decorator factory ────────────────────────────────────────────────

def cached(prefix: str, ttl: int | None = None):
    """Decorator factory for caching FastAPI endpoint responses.

    Usage::

        @router.get("/summary/sectors")
        @cached("sentiment:sectors", ttl=300)
        async def get_sector_summary(db=Depends(get_db), _user=Depends(...)):
            ...

    The decorator inspects function kwargs (excluding DI dependencies)
    to build the cache key automatically.
    """
    _ttl = ttl if ttl is not None else settings.cache_default_ttl

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.cache_enabled:
                return await func(*args, **kwargs)

            # Build key from non-dependency kwargs
            param_keys = {
                k: v for k, v in kwargs.items()
                if k not in ("db", "_user", "_admin", "response", "request")
            }
            key = cache_key(prefix, **param_keys)

            # Try cache hit
            hit = await get_cached(key)
            if hit is not None:
                return hit

            # Compute, cache, return
            result = await func(*args, **kwargs)
            serializable = _to_serializable(result)
            await set_cached(key, serializable, _ttl)
            return result

        return wrapper
    return decorator
