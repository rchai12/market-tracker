"""Health check endpoint with dependency verification.

Checks database and Redis connectivity. Returns component-level status
when ``?detail=true`` is passed. Unauthenticated for monitoring tools.
"""

import logging
import time

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _check_db(session: AsyncSession) -> dict:
    """Verify database connectivity and measure latency."""
    start = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "up", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.error("Health check: database down — %s", exc)
        return {"status": "down", "latency_ms": latency_ms, "error": str(exc)}


async def _check_redis() -> dict:
    """Verify Redis connectivity and measure latency."""
    start = time.perf_counter()
    try:
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=3)
        try:
            await client.ping()
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            return {"status": "up", "latency_ms": latency_ms}
        finally:
            await client.aclose()
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.error("Health check: redis down — %s", exc)
        return {"status": "down", "latency_ms": latency_ms, "error": str(exc)}


@router.get("/health")
async def health_check(
    response: Response,
    detail: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Health endpoint for monitoring and load balancers.

    Returns 200 if all dependencies are reachable, 503 otherwise.
    Pass ``?detail=true`` to see per-component status.
    """
    db_status = await _check_db(db)
    redis_status = await _check_redis()

    all_up = db_status["status"] == "up" and redis_status["status"] == "up"
    overall = "healthy" if all_up else "unhealthy"

    if not all_up:
        response.status_code = 503

    result: dict = {"status": overall, "service": "stock-predictor"}

    if detail or not all_up:
        result["components"] = {"database": db_status, "redis": redis_status}

    return result
