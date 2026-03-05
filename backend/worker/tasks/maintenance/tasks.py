"""Data retention and maintenance Celery tasks.

All tasks run via beat schedule (daily at 3 AM via run_all_maintenance).
Individual tasks are also callable from Flower or the admin API.
"""

import logging

from app.config import settings
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.maintenance.compress_old_articles",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def compress_old_articles(self):
    """Nullify raw_text on old processed articles to reclaim storage.

    Articles keep their title, summary, sentiment scores, and metadata.
    Only raw_text (the heaviest column) is removed.
    """
    try:
        return run_async(_compress_articles_async())
    except Exception as exc:
        logger.error("Article compression failed: %s", exc)
        raise self.retry(exc=exc)


async def _compress_articles_async() -> dict:
    from app.models.article import Article
    from worker.tasks.maintenance.retention import nullify_column_older_than

    updated = await nullify_column_older_than(
        model=Article,
        timestamp_column=Article.scraped_at,
        target_column=Article.raw_text,
        days=settings.retention_article_text_days,
    )
    logger.info("Article compression: nullified raw_text on %d articles", updated)
    return {"compressed": updated}


@celery_app.task(
    name="worker.tasks.maintenance.cleanup_scrape_logs",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def cleanup_scrape_logs(self):
    """Delete scrape_logs older than retention period."""
    try:
        return run_async(_cleanup_scrape_logs_async())
    except Exception as exc:
        logger.error("Scrape log cleanup failed: %s", exc)
        raise self.retry(exc=exc)


async def _cleanup_scrape_logs_async() -> dict:
    from app.models.scrape_log import ScrapeLog
    from worker.tasks.maintenance.retention import delete_older_than

    deleted = await delete_older_than(
        model=ScrapeLog,
        timestamp_column=ScrapeLog.started_at,
        days=settings.retention_scrape_log_days,
    )
    logger.info("Scrape log cleanup: deleted %d logs", deleted)
    return {"deleted": deleted}


@celery_app.task(
    name="worker.tasks.maintenance.cleanup_alert_logs",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def cleanup_alert_logs(self):
    """Delete alert_logs older than retention period."""
    try:
        return run_async(_cleanup_alert_logs_async())
    except Exception as exc:
        logger.error("Alert log cleanup failed: %s", exc)
        raise self.retry(exc=exc)


async def _cleanup_alert_logs_async() -> dict:
    from app.models.alert import AlertLog
    from worker.tasks.maintenance.retention import delete_older_than

    deleted = await delete_older_than(
        model=AlertLog,
        timestamp_column=AlertLog.sent_at,
        days=settings.retention_alert_log_days,
    )
    logger.info("Alert log cleanup: deleted %d logs", deleted)
    return {"deleted": deleted}


@celery_app.task(
    name="worker.tasks.maintenance.cleanup_old_signals",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def cleanup_old_signals(self):
    """Delete weak signals older than retention period.

    Moderate and strong signals are kept indefinitely for analytical value.
    """
    try:
        return run_async(_cleanup_signals_async())
    except Exception as exc:
        logger.error("Signal cleanup failed: %s", exc)
        raise self.retry(exc=exc)


async def _cleanup_signals_async() -> dict:
    from app.models.signal import Signal
    from worker.tasks.maintenance.retention import delete_older_than

    deleted = await delete_older_than(
        model=Signal,
        timestamp_column=Signal.generated_at,
        days=settings.retention_signal_days,
        extra_filters=[Signal.strength == "weak"],
    )
    logger.info("Signal cleanup: deleted %d weak signals", deleted)
    return {"deleted": deleted}


@celery_app.task(
    name="worker.tasks.maintenance.run_all_maintenance",
    bind=True,
    max_retries=0,
)
def run_all_maintenance(self):
    """Orchestrator: runs all cleanup tasks sequentially.

    Called by beat schedule daily at 3 AM. Sequential execution
    avoids concurrent heavy I/O on the free-tier VM.
    Each task is wrapped in try/except so one failure doesn't block others.
    """
    results = {}

    for name, coro_fn in [
        ("compress_articles", _compress_articles_async),
        ("scrape_logs", _cleanup_scrape_logs_async),
        ("alert_logs", _cleanup_alert_logs_async),
        ("signals", _cleanup_signals_async),
    ]:
        try:
            results[name] = run_async(coro_fn())
        except Exception as e:
            logger.error("Maintenance task %s failed: %s", name, e)
            results[name] = {"error": str(e)}

    logger.info("All maintenance complete: %s", results)
    return results


@celery_app.task(
    name="worker.tasks.maintenance.refresh_materialized_views",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def refresh_materialized_views(self):
    """Refresh materialized views after signal generation.

    Uses CONCURRENTLY to avoid locking reads during refresh.
    """
    try:
        return run_async(_refresh_views_async())
    except Exception as exc:
        logger.error("Materialized view refresh failed: %s", exc)
        raise self.retry(exc=exc)


async def _refresh_views_async() -> dict:
    from sqlalchemy import text

    from app.database import async_session

    async with async_session() as session:
        await session.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sentiment_summary")
        )
        await session.commit()

    logger.info("Materialized views refreshed")
    return {"refreshed": ["mv_daily_sentiment_summary"]}
