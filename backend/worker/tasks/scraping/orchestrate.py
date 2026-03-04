"""Orchestration task that fans out all scrapers and logs aggregate results."""

import logging

from celery import group

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

SCRAPERS = [
    "worker.tasks.scraping.orchestrate.scrape_yahoo_news",
    "worker.tasks.scraping.orchestrate.scrape_finviz",
    "worker.tasks.scraping.orchestrate.scrape_reuters",
    "worker.tasks.scraping.orchestrate.scrape_sec_edgar",
    "worker.tasks.scraping.orchestrate.scrape_marketwatch",
    "worker.tasks.scraping.orchestrate.scrape_reddit",
    "worker.tasks.scraping.orchestrate.scrape_fred",
]


@celery_app.task(name="worker.tasks.scraping.orchestrate_scraping", bind=True, max_retries=0)
def orchestrate_scraping(self):
    """Fan out all scrapers in parallel, then log aggregate results."""
    logger.info("Starting scrape orchestration")

    job = group(
        scrape_yahoo_news.s(),
        scrape_finviz.s(),
        scrape_reuters.s(),
        scrape_sec_edgar.s(),
        scrape_marketwatch.s(),
        scrape_reddit.s(),
        scrape_fred.s(),
    )

    result = job.apply_async()
    result.get(timeout=300, disable_sync_subtasks=False)

    total_new = sum(r for r in result.results if isinstance(r.result, int))
    logger.info(f"Scrape orchestration complete: {total_new} total new articles")
    return {"total_new_articles": total_new}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_yahoo_news(self):
    """Scrape Yahoo Finance news."""
    try:
        from worker.tasks.scraping.yahoo_news import YahooNewsScraper
        return YahooNewsScraper().run()
    except Exception as exc:
        logger.error(f"Yahoo News scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_finviz(self):
    """Scrape Finviz news."""
    try:
        from worker.tasks.scraping.finviz import FinvizScraper
        return FinvizScraper().run()
    except Exception as exc:
        logger.error(f"Finviz scrape failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def scrape_reuters(self):
    """Scrape Reuters RSS feeds."""
    try:
        from worker.tasks.scraping.reuters_rss import ReutersRssScraper
        return ReutersRssScraper().run()
    except Exception as exc:
        logger.error(f"Reuters scrape failed: {exc}")
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
