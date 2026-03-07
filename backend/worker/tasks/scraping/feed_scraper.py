"""Base class for RSS/Atom feed-based scrapers.

Provides common scrape (feedparser) and parse (dedup + date parsing) logic.
Subclasses only need to define feed URLs and source_name.
"""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class FeedScraper(BaseScraper):
    """Base scraper for RSS/Atom feeds. Subclasses set `source_name` and `feed_urls`."""

    feed_urls: list[str] = []

    def scrape(self) -> list[dict]:
        articles = []
        for feed_url in self.feed_urls:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    articles.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "author": entry.get("author", ""),
                        "source_detail": entry.get("source", {}),
                    })
            except Exception as e:
                logger.warning(f"Failed to parse feed {feed_url}: {e}")
        return articles

    def parse(self, raw_data: list[dict]) -> list[dict]:
        seen_urls: set[str] = set()
        parsed = []

        for item in raw_data:
            url = item.get("url", "")
            title = item.get("title", "").strip()

            if not title or not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            published_at = self._parse_date(item.get("published"))

            entry = {
                "source": self.source_name,
                "source_url": url,
                "title": title,
                "raw_text": item.get("summary") or None,
                "published_at": published_at or datetime.now(timezone.utc),
            }

            # Optional fields
            if item.get("author"):
                entry["author"] = item["author"]

            metadata = self._build_metadata(item)
            if metadata:
                entry["metadata"] = metadata

            parsed.append(entry)

        return parsed

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return datetime.now(timezone.utc)

    def _build_metadata(self, item: dict) -> dict | None:
        """Override to add source-specific metadata."""
        return None
