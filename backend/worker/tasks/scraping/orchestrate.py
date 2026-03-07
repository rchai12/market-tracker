"""Orchestration task that fans out all scrapers, then triggers sentiment analysis."""

import logging

from celery import group
from sqlalchemy import select

from app.database import async_session
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


async def _load_active_tickers() -> list[str]:
    """Load active stock tickers from the database."""
    async with async_session() as session:
        result = await session.execute(
            select(Stock.ticker).where(Stock.is_active == True)  # noqa: E712
        )
        return [row[0] for row in result.all()]


@celery_app.task(name="worker.tasks.scraping.orchestrate_scraping", bind=True, max_retries=0)
def orchestrate_scraping(self):
    """Fan out all scrapers in parallel, then chain sentiment processing."""
    from worker.tasks.sentiment.sentiment_task import process_new_articles_sentiment

    logger.info("Starting scrape orchestration")

    # Load tickers for scrapers that need them
    tickers = run_async(_load_active_tickers())
    logger.info(f"Loaded {len(tickers)} active tickers for scraping")

    scrape_job = group(
        scrape_yahoo_news.s(tickers),
        scrape_finviz.s(tickers),
        scrape_google_news.s(),
        scrape_sec_edgar.s(),
        scrape_marketwatch.s(),
        scrape_reddit.s(),
        scrape_fred.s(),
    )

    result = scrape_job.apply_async()
    result.get(timeout=300, disable_sync_subtasks=False)

    total_new = sum(r for r in result.results if isinstance(r.result, int))
    logger.info(f"Scrape orchestration complete: {total_new} total new articles")

    # Chain sentiment processing if new articles were found
    if total_new > 0:
        logger.info("Triggering sentiment analysis for new articles")
        process_new_articles_sentiment.delay()

    return {"total_new_articles": total_new}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_yahoo_news(self, tickers=None):
    """Scrape Yahoo Finance news."""
    try:
        from worker.tasks.scraping.yahoo_news import YahooNewsScraper
        return YahooNewsScraper(tickers=tickers).run()
    except Exception as exc:
        logger.error(f"Yahoo News scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_finviz(self, tickers=None):
    """Scrape Finviz news."""
    try:
        from worker.tasks.scraping.finviz import FinvizScraper
        return FinvizScraper(tickers=tickers).run()
    except Exception as exc:
        logger.error(f"Finviz scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_google_news(self):
    """Scrape Google News RSS for financial news."""
    try:
        from worker.tasks.scraping.google_news import GoogleNewsScraper
        return GoogleNewsScraper().run()
    except Exception as exc:
        logger.error(f"Google News scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_sec_edgar(self):
    """Scrape SEC EDGAR filings."""
    try:
        from worker.tasks.scraping.sec_edgar import SecEdgarScraper
        return SecEdgarScraper().run()
    except Exception as exc:
        logger.error(f"SEC EDGAR scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_marketwatch(self):
    """Scrape MarketWatch news."""
    try:
        from worker.tasks.scraping.marketwatch import MarketWatchScraper
        return MarketWatchScraper().run()
    except Exception as exc:
        logger.error(f"MarketWatch scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_reddit(self):
    """Scrape Reddit finance subreddits."""
    try:
        from worker.tasks.scraping.reddit import RedditScraper
        return RedditScraper().run()
    except Exception as exc:
        logger.error(f"Reddit scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_fred(self):
    """Scrape FRED economic data releases."""
    try:
        from worker.tasks.scraping.fred import FredScraper
        return FredScraper().run()
    except Exception as exc:
        logger.error(f"FRED scrape failed: {exc}")
        raise self.retry(exc=exc)
