"""Health check task: verifies DB, Redis, and Celery queue health.

Sends Discord webhook alerts when issues are detected, with throttling
to avoid notification spam.
"""

import logging
import time

import httpx
from sqlalchemy import text

from app.config import settings
from app.database import async_session
from worker.utils.celery_helpers import async_task

logger = logging.getLogger(__name__)

# Module-level throttle: min seconds between alerts
_last_alert_time: float = 0.0


@async_task("worker.tasks.maintenance.health_check", max_retries=0)
async def run_health_check():
    """Check DB, Redis, and queue health. Alert on failure via Discord webhook."""
    issues = []

    # 1. Database connectivity
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        issues.append(f"Database: {e}")
        logger.error("Health check: DB unreachable — %s", e)

    # 2. Redis connectivity
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
    except Exception as e:
        issues.append(f"Redis: {e}")
        logger.error("Health check: Redis unreachable — %s", e)

    # 3. Celery queue depths
    try:
        from worker.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=5)
        active_queues = inspect.active_queues() or {}
        reserved = inspect.reserved() or {}

        total_reserved = sum(len(tasks) for tasks in reserved.values())
        if total_reserved > 100:
            issues.append(f"Queue backlog: {total_reserved} tasks reserved")
            logger.warning("Health check: queue backlog — %d tasks", total_reserved)
    except Exception as e:
        issues.append(f"Celery inspect: {e}")
        logger.error("Health check: Celery inspect failed — %s", e)

    if issues:
        await _send_alert(issues)
    else:
        logger.debug("Health check: all systems OK")

    return {"status": "degraded" if issues else "healthy", "issues": issues}


async def _send_alert(issues: list[str]) -> None:
    """Send a Discord webhook embed if the alert cooldown has elapsed."""
    global _last_alert_time

    if not settings.health_alert_webhook_url:
        logger.debug("Health alert skipped: no webhook URL configured")
        return

    min_interval = settings.health_alert_min_interval_minutes * 60
    now = time.time()
    if now - _last_alert_time < min_interval:
        logger.debug("Health alert throttled (last alert %.0fs ago)", now - _last_alert_time)
        return

    embed = {
        "title": "Stock Predictor Health Alert",
        "color": 0xFF0000,
        "description": "\n".join(f"- {issue}" for issue in issues),
        "footer": {"text": "Health check task"},
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.health_alert_webhook_url,
                json={"embeds": [embed]},
            )
            resp.raise_for_status()
        _last_alert_time = now
        logger.info("Health alert sent: %d issues", len(issues))
    except Exception as e:
        logger.error("Failed to send health alert: %s", e)
