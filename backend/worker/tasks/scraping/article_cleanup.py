"""Post-scrape cleanup tasks.

Assigns canonical articles within duplicate groups and backfills quality scores.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from app.database import async_session
from app.models.article import Article, ArticleStock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.scraping.assign_canonical_articles",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def assign_canonical_articles(self):
    """Designate canonical articles within duplicate groups.

    Runs after all scrapers complete. Within each duplicate_group_id:
      - The article with the highest quality_score is canonical
        (its canonical_article_id is set to NULL).
      - All other members get canonical_article_id = id of the canonical article.

    Only processes articles scraped in the last 48 hours.
    """
    try:
        return run_async(_assign_canonical_async())
    except Exception as exc:
        logger.error(f"Canonical assignment failed: {exc}")
        raise self.retry(exc=exc)


async def _assign_canonical_async() -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    groups_processed = 0
    articles_updated = 0

    async with async_session() as session:
        result = await session.execute(
            select(Article.id, Article.duplicate_group_id, Article.quality_score)
            .where(Article.scraped_at >= since)
            .where(Article.duplicate_group_id.isnot(None))
            .order_by(Article.duplicate_group_id)
        )
        rows = result.all()

        if not rows:
            logger.info("Canonical assignment: no duplicate groups in last 48h")
            return {"groups_processed": 0, "articles_updated": 0}

        # Build groups: duplicate_group_id -> list of (article_id, quality_score)
        groups: dict[int, list[tuple[int, float]]] = {}
        for row in rows:
            quality = float(row.quality_score) if row.quality_score is not None else 0.5
            groups.setdefault(row.duplicate_group_id, []).append((row.id, quality))

        for _group_id, members in groups.items():
            groups_processed += 1

            if len(members) == 1:
                # Single member — ensure it is marked canonical
                await session.execute(
                    update(Article).where(Article.id == members[0][0]).values(canonical_article_id=None)
                )
                continue

            # Sort descending by quality; highest quality is canonical
            members.sort(key=lambda x: x[1], reverse=True)
            canonical_id = members[0][0]
            duplicate_ids = [m[0] for m in members[1:]]

            # Canonical article: clear any stale canonical_article_id
            await session.execute(
                update(Article).where(Article.id == canonical_id).values(canonical_article_id=None)
            )

            # Duplicate articles: point to canonical
            await session.execute(
                update(Article).where(Article.id.in_(duplicate_ids)).values(canonical_article_id=canonical_id)
            )

            articles_updated += len(duplicate_ids)

        await session.commit()

    logger.info(
        f"Canonical assignment complete: {groups_processed} groups, "
        f"{articles_updated} articles marked as duplicates"
    )
    return {"groups_processed": groups_processed, "articles_updated": articles_updated}


@celery_app.task(
    name="worker.tasks.scraping.backfill_article_quality_scores",
    bind=True,
    max_retries=0,
)
def backfill_article_quality_scores(self):
    """Backfill quality_score for all articles where quality_score IS NULL.

    Admin-triggered. Processes in batches of 500 to avoid memory pressure.
    """
    try:
        return run_async(_backfill_quality_async())
    except Exception as exc:
        logger.error(f"Quality score backfill failed: {exc}")
        raise


async def _backfill_quality_async() -> dict:
    from app.config import DEFAULT_SOURCE_CREDIBILITY, SOURCE_CREDIBILITY
    from worker.utils.article_quality import compute_article_quality

    batch_size = 500
    total_processed = 0

    while True:
        async with async_session() as session:
            # Fetch next batch of articles missing quality_score
            result = await session.execute(
                select(Article.id, Article.source, Article.raw_text)
                .where(Article.quality_score.is_(None))
                .limit(batch_size)
            )
            articles = result.all()

            if not articles:
                break

            article_ids = [a.id for a in articles]

            # Get max ArticleStock confidence per article in this batch
            conf_result = await session.execute(
                select(
                    ArticleStock.article_id,
                    func.max(ArticleStock.confidence).label("max_conf"),
                )
                .where(ArticleStock.article_id.in_(article_ids))
                .group_by(ArticleStock.article_id)
            )
            conf_map = {row.article_id: float(row.max_conf) for row in conf_result.all()}

            for article in articles:
                max_conf = conf_map.get(article.id, 0.0)
                quality = compute_article_quality(
                    source=article.source,
                    raw_text=article.raw_text,
                    max_ticker_confidence=max_conf,
                    source_credibility_map=SOURCE_CREDIBILITY,
                    default_credibility=DEFAULT_SOURCE_CREDIBILITY,
                )
                await session.execute(
                    update(Article).where(Article.id == article.id).values(quality_score=quality)
                )

            await session.commit()
            total_processed += len(articles)
            logger.info(f"Quality backfill: {total_processed} articles processed so far")

    logger.info(f"Quality backfill complete: {total_processed} total articles")
    return {"articles_processed": total_processed}
