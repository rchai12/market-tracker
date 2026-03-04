"""Yahoo Finance news scraper."""

import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

YAHOO_NEWS_URL = "https://finance.yahoo.com/news/"
YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{ticker}/news/"


class YahooNewsScraper(BaseScraper):
    source_name = "yahoo_finance"

    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or []

    def scrape(self) -> list[dict]:
        articles = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Scrape general finance news
        try:
            resp = httpx.get(YAHOO_NEWS_URL, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            articles.extend(self._extract_articles(resp.text))
        except Exception as e:
            logger.warning(f"Failed to fetch Yahoo general news: {e}")

        # Scrape per-ticker news for key tickers
        for ticker in self.tickers[:10]:  # limit to avoid rate issues
            try:
                url = YAHOO_QUOTE_URL.format(ticker=ticker)
                resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                articles.extend(self._extract_articles(resp.text))
            except Exception as e:
                logger.warning(f"Failed to fetch Yahoo news for {ticker}: {e}")

        return articles

    def _extract_articles(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        articles = []

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            title_tag = link.find(["h3", "h4"]) or link
            title = title_tag.get_text(strip=True)

            if not title or len(title) < 15:
                continue
            if "/news/" not in href and "/m/" not in href:
                continue

            url = href if href.startswith("http") else f"https://finance.yahoo.com{href}"

            articles.append({
                "url": url,
                "title": title,
            })

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
                "raw_text": None,  # full text would require per-article fetch
                "published_at": datetime.now(timezone.utc),
            })

        return parsed
