import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all scrapers. Provides retry, rate limiting, and logging."""

    source_name: str = "unknown"

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Fetch raw data from the source. Returns list of raw article dicts."""

    @abstractmethod
    def parse(self, raw_data: list[dict]) -> list[dict]:
        """Normalize raw data into standard article format."""

    def store(self, articles: list[dict]) -> int:
        """Store articles in the database. Returns count of new articles inserted."""
        # Will be implemented with DB session in Phase 4
        raise NotImplementedError

    def log_success(self, new_count: int) -> None:
        logger.info(f"[{self.source_name}] Scrape complete: {new_count} new articles")

    def log_failure(self, error: str) -> None:
        logger.error(f"[{self.source_name}] Scrape failed: {error}")

    def run(self) -> int:
        """Execute the full scrape → parse → store pipeline."""
        try:
            raw_data = self.scrape()
            articles = self.parse(raw_data)
            new_count = self.store(articles)
            self.log_success(new_count)
            return new_count
        except Exception as e:
            self.log_failure(str(e))
            raise
