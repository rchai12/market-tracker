"""Reusable data retention utilities.

Provides batched async functions for age-based data cleanup.
All maintenance tasks use these to avoid duplication.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session

logger = logging.getLogger(__name__)

# Max rows per batch — keeps transactions short to avoid WAL bloat
# and connection pool exhaustion on free-tier Postgres.
DELETE_BATCH_SIZE = 1000


async def delete_older_than(
    model,
    timestamp_column,
    days: int,
    *,
    extra_filters: list | None = None,
    batch_size: int = DELETE_BATCH_SIZE,
) -> int:
    """Delete rows older than ``days`` from ``model``, in batches.

    Returns total number of rows deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total_deleted = 0

    async with async_session() as session:
        while True:
            id_query = select(model.id).where(timestamp_column < cutoff)
            if extra_filters:
                for f in extra_filters:
                    id_query = id_query.where(f)
            id_query = id_query.limit(batch_size)

            result = await session.execute(id_query)
            ids = [row[0] for row in result.all()]
            if not ids:
                break

            stmt = delete(model).where(model.id.in_(ids))
            result = await session.execute(stmt)
            await session.commit()
            total_deleted += result.rowcount

    if total_deleted:
        logger.info("Retention: deleted %d rows from %s", total_deleted, model.__tablename__)
    return total_deleted


async def nullify_column_older_than(
    model,
    timestamp_column,
    target_column,
    days: int,
    *,
    batch_size: int = DELETE_BATCH_SIZE,
) -> int:
    """Set ``target_column`` to NULL for rows older than ``days``, in batches.

    Used for article text compression — drops ``raw_text`` on old articles
    while keeping metadata, title, summary, and sentiment scores intact.

    Returns total number of rows updated.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total_updated = 0

    async with async_session() as session:
        while True:
            id_query = (
                select(model.id)
                .where(timestamp_column < cutoff)
                .where(target_column.isnot(None))
                .limit(batch_size)
            )
            result = await session.execute(id_query)
            ids = [row[0] for row in result.all()]
            if not ids:
                break

            stmt = update(model).where(model.id.in_(ids)).values({target_column.key: None})
            result = await session.execute(stmt)
            await session.commit()
            total_updated += result.rowcount

    if total_updated:
        logger.info(
            "Retention: nullified %s on %d rows in %s",
            target_column.key,
            total_updated,
            model.__tablename__,
        )
    return total_updated
