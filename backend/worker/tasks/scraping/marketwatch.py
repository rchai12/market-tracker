"""MarketWatch news scraper."""

import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

MARKETWATCH_URL = "https://www.marketwatch.com/latest-news"


class MarketWatchScraper(BaseScraper):
    source_name = "marketwatch"

    def scrape(self) -> list[dict]:
        articles = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            resp = httpx.get(MARKETWATCH_URL, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for article in soup.find_all("div", class_="article__content"):
                link = article.find("a", class_="link")
                if not link:
                    link = article.find("a")
                if not link:
                    continue

                title = link.get_text(strip=True)
                url = link.get("href", "")

                if not title or len(title) < 10:
                    continue

                if not url.startswith("http"):
                    url = f"https://www.marketwatch.com{url}"

                # Try to get summary
                summary_tag = article.find("p", class_="article__summary")
                summary = summary_tag.get_text(strip=True) if summary_tag else None

                articles.append({
                    "title": title,
                    "url": url,
                    "summary": summary,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch MarketWatch: {e}")

        return articles

    def parse(self, raw_data: list[dict]) -> list[dict]:
        seen_urls = set()
        parsed = []

        for item in raw_data:
            url = item.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            parsed.append({
                "source": self.source_name,
                "source_url": url,
                "title": item["title"],
                "raw_text": item.get("summary"),
                "published_at": datetime.now(timezone.utc),
            })

        return parsed
