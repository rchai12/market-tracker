import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.article import Article, ArticleStock
from app.models.scrape_log import ScrapeLog
from app.models.stock import Stock
from worker.utils.async_task import run_async
from worker.utils.text_cleaner import clean_article_text
from worker.utils.ticker_extractor import build_company_map, extract_tickers

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

    async def _store_async(self, articles: list[dict]) -> int:
        """Async storage with deduplication by source_url."""
        if not articles:
            return 0

        new_count = 0
        async with async_session() as session:
            # Load known tickers and company names for extraction
            result = await session.execute(select(Stock.ticker, Stock.id, Stock.company_name))
            rows = result.all()
            ticker_map = {row.ticker: row.id for row in rows}
            known_tickers = set(ticker_map.keys())
            company_map = build_company_map([(row.ticker, row.company_name) for row in rows])

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
                    company_map=company_map,
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

    def run(self) -> int:
        """Execute the full scrape -> parse -> store pipeline."""
        return run_async(self._run_async())

    async def _run_async(self) -> int:
        """Run the full pipeline in a single async context to avoid cross-loop issues."""
        try:
            raw_data = self.scrape()
            articles = self.parse(raw_data)
            new_count = await self._store_async(articles)
            await self._log_result_async(len(raw_data), new_count, 0, None)
            logger.info(f"[{self.source_name}] Scrape complete: {new_count} new articles")
            return new_count
        except Exception as e:
            await self._log_result_async(0, 0, 1, str(e))
            logger.error(f"[{self.source_name}] Scrape failed: {e}")
            raise
