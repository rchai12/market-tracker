"""SQLAlchemy event listeners for slow query detection.

Logs queries exceeding the configurable threshold to structured JSON logs.
Attach to the engine via ``attach_slow_query_listener()`` at startup.
"""

import logging
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings

logger = logging.getLogger("app.slow_query")


def attach_slow_query_listener(engine: AsyncEngine) -> None:
    """Attach before/after cursor execute event listeners to detect slow queries."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get("query_start_time", [])
        if not start_times:
            return
        start = start_times.pop()
        duration_ms = (time.perf_counter() - start) * 1000

        if duration_ms >= settings.slow_query_threshold_ms:
            truncated = statement[:500] + ("..." if len(statement) > 500 else "")
            logger.warning(
                "slow_query duration_ms=%.1f query=%s",
                duration_ms,
                truncated,
            )
