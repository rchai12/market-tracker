"""Celery task to process unprocessed articles through FinBERT."""

import asyncio
import logging

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.article import Article, ArticleStock
from app.models.sentiment import SentimentScore
from worker.celery_app import celery_app
from worker.tasks.sentiment.finbert_analyzer import FinBERTAnalyzer

logger = logging.getLogger(__name__)

# Process articles in DB query batches
QUERY_BATCH_SIZE = 50


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def process_new_articles_sentiment(self):
    """Find unprocessed articles, run FinBERT, store sentiment scores."""
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_process_sentiment_async())
        return result
    except Exception as exc:
        logger.error(f"Sentiment processing failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()


async def _process_sentiment_async() -> dict:
    """Fetch unprocessed articles and score them with FinBERT."""
    analyzer = FinBERTAnalyzer()

    total_processed = 0
    total_scores = 0
    errors = 0

    async with async_session() as session:
        # Count unprocessed
        count_result = await session.execute(
            select(func.count(Article.id)).where(Article.is_processed == False)  # noqa: E712
        )
        unprocessed_count = count_result.scalar() or 0

        if unprocessed_count == 0:
            logger.info("No unprocessed articles found")
            return {"processed": 0, "scores": 0, "errors": 0}

        logger.info(f"Processing {unprocessed_count} unprocessed articles")

        # Process in batches
        offset = 0
        while True:
            result = await session.execute(
                select(Article)
                .where(Article.is_processed == False)  # noqa: E712
                .options(selectinload(Article.article_stocks))
                .order_by(Article.id)
                .offset(offset)
                .limit(QUERY_BATCH_SIZE)
            )
            articles = result.scalars().unique().all()

            if not articles:
                break

            # Prepare texts for batch inference
            texts = []
            for article in articles:
                text = _get_analysis_text(article)
                texts.append(text)

            # Run FinBERT batch inference
            try:
                sentiments = analyzer.analyze_batch(texts)
            except Exception as e:
                logger.error(f"FinBERT batch inference failed: {e}")
                errors += len(articles)
                offset += QUERY_BATCH_SIZE
                continue

            # Store sentiment scores
            for article, sentiment in zip(articles, sentiments):
                try:
                    await _store_sentiment(session, article, sentiment)
                    total_scores += max(1, len(article.article_stocks))
                except Exception as e:
                    logger.error(f"Failed to store sentiment for article {article.id}: {e}")
                    errors += 1

                # Mark article as processed
                article.is_processed = True
                total_processed += 1

            await session.commit()
            offset += QUERY_BATCH_SIZE

    logger.info(f"Sentiment processing complete: {total_processed} articles, {total_scores} scores, {errors} errors")
    return {"processed": total_processed, "scores": total_scores, "errors": errors}


def _get_analysis_text(article: Article) -> str:
    """Extract the best text for sentiment analysis from an article."""
    # Prefer raw_text (full article body), fall back to title
    if article.raw_text and len(article.raw_text) > 20:
        return article.raw_text
    if article.summary and len(article.summary) > 20:
        return article.summary
    return article.title


async def _store_sentiment(session, article: Article, sentiment: dict):
    """Store sentiment score(s) for an article.

    If the article is linked to stocks (via article_stocks), create a score per stock.
    Otherwise, create one score with stock_id=None (general sentiment).
    """
    if article.article_stocks:
        for article_stock in article.article_stocks:
            # Check for existing score (unique constraint: article_id + stock_id)
            existing = await session.execute(
                select(SentimentScore.id).where(
                    SentimentScore.article_id == article.id,
                    SentimentScore.stock_id == article_stock.stock_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            score = SentimentScore(
                article_id=article.id,
                stock_id=article_stock.stock_id,
                label=sentiment["label"],
                positive_score=sentiment["positive"],
                negative_score=sentiment["negative"],
                neutral_score=sentiment["neutral"],
            )
            session.add(score)
    else:
        # No linked stocks — store as general sentiment
        existing = await session.execute(
            select(SentimentScore.id).where(
                SentimentScore.article_id == article.id,
                SentimentScore.stock_id == None,  # noqa: E711
            )
        )
        if existing.scalar_one_or_none() is None:
            score = SentimentScore(
                article_id=article.id,
                stock_id=None,
                label=sentiment["label"],
                positive_score=sentiment["positive"],
                negative_score=sentiment["negative"],
                neutral_score=sentiment["neutral"],
            )
            session.add(score)
