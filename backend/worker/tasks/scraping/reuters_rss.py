"""Reuters RSS feed scraper."""

import logging
from datetime import datetime, timezone

import feedparser

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

REUTERS_FEEDS = [
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "https://www.reutersagency.com/feed/?best-topics=markets&post_type=best",
]


class ReutersRssScraper(BaseScraper):
    source_name = "reuters"

    def scrape(self) -> list[dict]:
        articles = []

        for feed_url in REUTERS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    articles.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "author": entry.get("author", ""),
                    })
            except Exception as e:
                logger.warning(f"Failed to parse Reuters feed {feed_url}: {e}")

        return articles

    def parse(self, raw_data: list[dict]) -> list[dict]:
        seen_urls = set()
        parsed = []

        for item in raw_data:
            url = item.get("url", "")
            title = item.get("title", "").strip()

            if not title or not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Parse published date
            published_at = None
            if item.get("published"):
                try:
                    from email.utils import parsedate_to_datetime
                    published_at = parsedate_to_datetime(item["published"])
                except Exception:
                    published_at = datetime.now(timezone.utc)

            parsed.append({
                "source": self.source_name,
                "source_url": url,
                "title": title,
                "raw_text": item.get("summary"),
                "author": item.get("author"),
                "published_at": published_at or datetime.now(timezone.utc),
            })

        return parsed
