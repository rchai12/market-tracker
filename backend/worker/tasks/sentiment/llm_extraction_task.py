"""Celery task: run LLM extraction on unprocessed earnings articles.

Finds articles where:
  - event_category = 'earnings'
  - llm_extracted IS NULL (not yet attempted)
  - quality_score >= QUALITY_THRESHOLD (or NULL, for legacy articles)
  - source NOT in SIGNAL_EXCLUDED_SOURCES (no Reddit)
  - canonical_article_id IS NULL (canonical only, no duplicates)
  - published_at within last 7 days (recent only)

For each article:
  1. Calls Claude Haiku → {guidance_change, management_tone}
  2. Stores management_tone in article.metadata_["management_tone"]
  3. Finds matching EarningsEstimate (same ticker, earnings_date within ±7 days of published_at)
  4. If found, updates guidance_change on the EarningsEstimate
  5. Marks article.llm_extracted = True

Runs at :20 (after sentiment at :15, before signals at :30).
Skipped entirely when LLM_EXTRACTION_ENABLED=false.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.article import Article, ArticleStock
from app.models.earnings_estimate import EarningsEstimate
from worker.celery_app import celery_app
from worker.utils.article_quality import QUALITY_THRESHOLD, SIGNAL_EXCLUDED_SOURCES
from worker.utils.async_task import run_async
from worker.utils.llm_extractor import extract_earnings_context

logger = logging.getLogger(__name__)

RECENT_DAYS = 7  # Only process articles published within this window
EARNINGS_MATCH_DAYS = 7  # Match article to EarningsEstimate within ±N days


@celery_app.task(
    name="worker.tasks.sentiment.llm_extraction_task.run_llm_extraction",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def run_llm_extraction(self):
    """LLM extraction pass on recent unprocessed earnings articles."""
    if not settings.llm_extraction_enabled:
        logger.debug("LLM extraction disabled — skipping")
        return {"skipped": True, "reason": "llm_extraction_disabled"}

    if not settings.anthropic_api_key:
        logger.warning("LLM extraction enabled but ANTHROPIC_API_KEY not set — skipping")
        return {"skipped": True, "reason": "no_api_key"}

    try:
        return run_async(_run_extraction_async())
    except Exception as exc:
        logger.error(f"LLM extraction task failed: {exc}")
        raise self.retry(exc=exc)


async def _run_extraction_async() -> dict:
    """Main extraction loop."""
    since = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)

    async with async_session() as session:
        result = await session.execute(
            select(Article)
            .options(selectinload(Article.article_stocks).selectinload(ArticleStock.stock))
            .where(Article.event_category == "earnings")
            .where(Article.llm_extracted.is_(None))  # not yet attempted
            .where(Article.canonical_article_id.is_(None))  # canonical only
            .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))  # no Reddit
            .where(
                (Article.quality_score >= QUALITY_THRESHOLD)
                | (Article.quality_score.is_(None))  # legacy articles without score
            )
            .where(Article.published_at >= since)
            .order_by(Article.published_at.desc())
            .limit(50)  # no longer RPD-constrained
        )
        articles = result.scalars().unique().all()

    logger.info(f"LLM extraction: {len(articles)} articles to process")

    extracted = 0
    skipped = 0
    errors = 0

    for article in articles:
        try:
            text = article.raw_text or article.summary or ""
            if not text.strip():
                async with async_session() as session:
                    art = await session.get(Article, article.id)
                    if art is None:
                        continue
                    art.llm_extracted = False
                    skipped += 1
                    await session.commit()
                continue

            result = extract_earnings_context(
                title=article.title,
                article_text=text,
                max_chars=settings.llm_max_article_chars,
            )

            async with async_session() as session:
                art = await session.get(Article, article.id)
                if art is None:
                    continue

                if result is None:
                    # API call failed — mark as attempted (False) to avoid retrying
                    art.llm_extracted = False
                    errors += 1
                else:
                    guidance = result.get("guidance_change")
                    tone = result.get("management_tone")

                    # Store management tone in metadata JSONB
                    if tone:
                        meta = dict(art.metadata_ or {})
                        meta["management_tone"] = tone
                        art.metadata_ = meta

                    # Update matching EarningsEstimate if guidance was found
                    if guidance and guidance != "none":
                        await _update_earnings_guidance(session, article, guidance)
                    else:
                        skipped += 1

                    art.llm_extracted = True
                    extracted += 1

                await session.commit()

        except Exception as e:
            logger.error(f"Error processing article {article.id}: {e}")
            errors += 1

        time.sleep(settings.llm_rate_limit_seconds)

    logger.info(
        f"LLM extraction complete: {extracted} extracted, {skipped} skipped, {errors} errors"
    )
    return {"extracted": extracted, "skipped": skipped, "errors": errors}


async def _update_earnings_guidance(session, article: Article, guidance_change: str) -> None:
    """Find the EarningsEstimate closest to the article's publish date and update guidance_change.

    Only updates records where guidance_change is currently NULL — never overwrites.
    Matches by stock_id (via ArticleStock) and earnings_date within ±EARNINGS_MATCH_DAYS.
    """
    if not article.published_at:
        return

    pub_date = article.published_at.date() if hasattr(article.published_at, "date") else article.published_at
    window_start = pub_date - timedelta(days=EARNINGS_MATCH_DAYS)
    window_end = pub_date + timedelta(days=EARNINGS_MATCH_DAYS)

    # Get stock_ids linked to this article
    ar_result = await session.execute(
        select(ArticleStock.stock_id).where(ArticleStock.article_id == article.id)
    )
    stock_ids = [r.stock_id for r in ar_result.all()]

    if not stock_ids:
        return

    for stock_id in stock_ids:
        # Find closest matching EarningsEstimate within the date window
        ee_result = await session.execute(
            select(EarningsEstimate)
            .where(EarningsEstimate.stock_id == stock_id)
            .where(EarningsEstimate.earnings_date >= window_start)
            .where(EarningsEstimate.earnings_date <= window_end)
            .where(EarningsEstimate.guidance_change.is_(None))  # don't overwrite
            .order_by(EarningsEstimate.earnings_date.asc())
            .limit(1)
        )
        ee = ee_result.scalar_one_or_none()

        if ee is not None:
            ee.guidance_change = guidance_change
            logger.debug(
                f"Updated guidance_change={guidance_change} on EarningsEstimate "
                f"id={ee.id} (stock_id={stock_id}, date={ee.earnings_date})"
            )
