import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.article import Article, ArticleStock
from app.models.scrape_log import ScrapeLog
from app.models.stock import Stock
from worker.utils.text_cleaner import clean_article_text
from worker.utils.ticker_extractor import extract_tickers

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all scrapers. Provides storage, dedup, ticker extraction, and logging."""

    source_name: str = "unknown"

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Fetch raw data from the source. Returns list of raw article dicts."""

    @abstractmethod
    def parse(self, raw_data: list[dict]) -> list[dict]:
        """Normalize raw data into standard article format.

        Each dict must have: source, title
        Optional: source_url, raw_text, author, published_at, metadata
        """

    def store(self, articles: list[dict]) -> int:
        """Store articles in the database. Returns count of new articles inserted."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._store_async(articles))
        finally:
            loop.close()

    async def _store_async(self, articles: list[dict]) -> int:
        """Async storage with deduplication by source_url."""
        if not articles:
            return 0

        new_count = 0
        async with async_session() as session:
            # Load known tickers for extraction
            result = await session.execute(select(Stock.ticker, Stock.id))
            ticker_map = {row.ticker: row.id for row in result.all()}
            known_tickers = set(ticker_map.keys())

            for article_data in articles:
                source_url = article_data.get("source_url")

                # Deduplicate by URL
                if source_url:
                    existing = await session.execute(
                        select(Article.id).where(Article.source_url == source_url)
                    )
                    if existing.scalar_one_or_none() is not None:
                        continue

                raw_text = clean_article_text(article_data.get("raw_text"))

                article = Article(
                    source=self.source_name,
                    source_url=source_url,
                    title=article_data["title"],
                    raw_text=raw_text,
                    author=article_data.get("author"),
                    published_at=article_data.get("published_at"),
                    metadata_=article_data.get("metadata", {}),
                    is_processed=False,
                )
                session.add(article)
                await session.flush()

                # Extract and link tickers
                tickers = extract_tickers(
                    article_data["title"],
                    raw_text,
                    known_tickers,
                )
                for ticker, confidence in tickers:
                    stock_id = ticker_map.get(ticker)
                    if stock_id:
                        await session.execute(
                            pg_insert(ArticleStock)
                            .values(article_id=article.id, stock_id=stock_id, confidence=confidence)
                            .on_conflict_do_nothing()
                        )

                new_count += 1

            await session.commit()
        return new_count

    def log_result(self, articles_found: int, new_count: int, errors: int = 0, error_details: str | None = None):
        """Log scrape result to scrape_logs table."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._log_result_async(articles_found, new_count, errors, error_details)
            )
        finally:
            loop.close()

    async def _log_result_async(
        self, articles_found: int, new_count: int, errors: int, error_details: str | None
    ):
        async with async_session() as session:
            log = ScrapeLog(
                source=self.source_name,
                completed_at=datetime.now(timezone.utc),
                articles_found=articles_found,
                articles_new=new_count,
                errors=errors,
                error_details=error_details,
                success=errors == 0,
            )
            session.add(log)
            await session.commit()

    def log_success(self, new_count: int) -> None:
        logger.info(f"[{self.source_name}] Scrape complete: {new_count} new articles")

    def log_failure(self, error: str) -> None:
        logger.error(f"[{self.source_name}] Scrape failed: {error}")

    def run(self) -> int:
        """Execute the full scrape -> parse -> store pipeline."""
        try:
            raw_data = self.scrape()
            articles = self.parse(raw_data)
            new_count = self.store(articles)
            self.log_result(len(raw_data), new_count)
            self.log_success(new_count)
            return new_count
        except Exception as e:
            self.log_result(0, 0, errors=1, error_details=str(e))
            self.log_failure(str(e))
            raise
