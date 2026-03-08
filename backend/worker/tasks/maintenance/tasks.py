"""Data retention and maintenance Celery tasks.

All tasks run via beat schedule (daily at 3 AM via run_all_maintenance).
Individual tasks are also callable from Flower or the admin API.
"""

import logging

from app.config import settings
from worker.celery_app import celery_app
from worker.utils.celery_helpers import async_task

logger = logging.getLogger(__name__)


@async_task("worker.tasks.maintenance.compress_old_articles", max_retries=1, retry_delay=120)
async def compress_old_articles():
    """Nullify raw_text on old processed articles to reclaim storage.

    Articles keep their title, summary, sentiment scores, and metadata.
    Only raw_text (the heaviest column) is removed.
    """
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


@async_task("worker.tasks.maintenance.cleanup_scrape_logs", max_retries=1, retry_delay=120)
async def cleanup_scrape_logs():
    """Delete scrape_logs older than retention period."""
    from app.models.scrape_log import ScrapeLog
    from worker.tasks.maintenance.retention import delete_older_than

    deleted = await delete_older_than(
        model=ScrapeLog,
        timestamp_column=ScrapeLog.started_at,
        days=settings.retention_scrape_log_days,
    )
    logger.info("Scrape log cleanup: deleted %d logs", deleted)
    return {"deleted": deleted}


@async_task("worker.tasks.maintenance.cleanup_alert_logs", max_retries=1, retry_delay=120)
async def cleanup_alert_logs():
    """Delete alert_logs older than retention period."""
    from app.models.alert import AlertLog
    from worker.tasks.maintenance.retention import delete_older_than

    deleted = await delete_older_than(
        model=AlertLog,
        timestamp_column=AlertLog.sent_at,
        days=settings.retention_alert_log_days,
    )
    logger.info("Alert log cleanup: deleted %d logs", deleted)
    return {"deleted": deleted}


@async_task("worker.tasks.maintenance.cleanup_old_signals", max_retries=1, retry_delay=120)
async def cleanup_old_signals():
    """Delete weak signals older than retention period.

    Moderate and strong signals are kept indefinitely for analytical value.
    """
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


@async_task("worker.tasks.maintenance.cleanup_options_data", max_retries=1, retry_delay=120)
async def cleanup_options_data():
    """Delete options_activity rows older than retention period."""
    from app.models.options_activity import OptionsActivity
    from worker.tasks.maintenance.retention import delete_older_than

    deleted = await delete_older_than(
        model=OptionsActivity,
        timestamp_column=OptionsActivity.created_at,
        days=settings.retention_options_days,
    )
    logger.info("Options data cleanup: deleted %d rows", deleted)

    # Also clean CBOE data (keep 365 days)
    from app.models.cboe_put_call import CboePutCallRatio

    deleted_cboe = await delete_older_than(
        model=CboePutCallRatio,
        timestamp_column=CboePutCallRatio.created_at,
        days=365,
    )
    logger.info("CBOE ratio cleanup: deleted %d rows", deleted_cboe)
    return {"options_deleted": deleted, "cboe_deleted": deleted_cboe}


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

    for name, task_fn in [
        ("compress_articles", compress_old_articles),
        ("scrape_logs", cleanup_scrape_logs),
        ("alert_logs", cleanup_alert_logs),
        ("signals", cleanup_old_signals),
        ("options_data", cleanup_options_data),
    ]:
        try:
            results[name] = task_fn()
        except Exception as e:
            logger.error("Maintenance task %s failed: %s", name, e)
            results[name] = {"error": str(e)}

    logger.info("All maintenance complete: %s", results)
    return results


@async_task("worker.tasks.maintenance.backfill_event_categories", max_retries=0)
async def backfill_event_categories():
    """Classify articles that have no event_category set. Admin-triggered."""
    from sqlalchemy import select, update

    from app.database import async_session
    from app.models.article import Article
    from worker.utils.event_classifier import classify_event

    updated = 0
    batch_size = 500
    async with async_session() as session:
        while True:
            result = await session.execute(
                select(Article.id, Article.title, Article.raw_text, Article.source)
                .where(Article.event_category == None)  # noqa: E711
                .limit(batch_size)
            )
            rows = result.all()
            if not rows:
                break

            for row in rows:
                category = classify_event(row.title, row.raw_text, row.source)
                await session.execute(
                    update(Article).where(Article.id == row.id).values(event_category=category)
                )
                updated += 1

            await session.commit()

    logger.info("Event category backfill: classified %d articles", updated)
    return {"classified": updated}


@async_task("worker.tasks.maintenance.backfill_duplicate_groups", max_retries=0)
async def backfill_duplicate_groups(days: int = 7):
    """Detect duplicate articles from the last N days. Admin-triggered."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import and_, select, update

    from app.database import async_session
    from app.models.article import Article, ArticleStock
    from worker.utils.duplicate_detector import find_duplicate_group

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    updated = 0

    async with async_session() as session:
        result = await session.execute(
            select(Article.id, Article.title, Article.scraped_at)
            .where(and_(Article.scraped_at >= cutoff, Article.duplicate_group_id == None))  # noqa: E711
            .order_by(Article.scraped_at.asc())
        )
        articles = result.all()

        for article in articles:
            window_start = article.scraped_at - timedelta(hours=24)
            recent_q = (
                select(Article.id, Article.title, Article.duplicate_group_id)
                .join(ArticleStock, ArticleStock.article_id == Article.id)
                .where(
                    and_(
                        Article.scraped_at >= window_start,
                        Article.scraped_at <= article.scraped_at,
                        Article.id != article.id,
                        ArticleStock.stock_id.in_(
                            select(ArticleStock.stock_id).where(ArticleStock.article_id == article.id)
                        ),
                    )
                )
                .distinct()
            )
            recent_result = await session.execute(recent_q)
            recent_articles = [(r.id, r.title, r.duplicate_group_id) for r in recent_result.all()]

            if recent_articles:
                group_id = find_duplicate_group(article.title, recent_articles, settings.duplicate_similarity_threshold)
                if group_id is not None:
                    await session.execute(
                        update(Article).where(Article.id == article.id).values(duplicate_group_id=group_id)
                    )
                    updated += 1

        await session.commit()

    logger.info("Duplicate group backfill: grouped %d articles over %d days", updated, days)
    return {"grouped": updated, "days": days}


@async_task("worker.tasks.maintenance.refresh_materialized_views", max_retries=1, retry_delay=60)
async def refresh_materialized_views():
    """Refresh materialized views. Uses CONCURRENTLY to avoid locking reads."""
    from sqlalchemy import text

    from app.database import async_session

    async with async_session() as session:
        await session.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sentiment_summary")
        )
        await session.commit()

    logger.info("Materialized views refreshed")
    return {"refreshed": ["mv_daily_sentiment_summary"]}
