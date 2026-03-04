"""Finviz news scraper."""

import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

FINVIZ_NEWS_URL = "https://finviz.com/news.ashx"
FINVIZ_QUOTE_URL = "https://finviz.com/quote.ashx?t={ticker}"


class FinvizScraper(BaseScraper):
    source_name = "finviz"

    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or []

    def scrape(self) -> list[dict]:
        articles = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Per-ticker news (Finviz has ticker-specific news tables)
        for ticker in self.tickers[:20]:
            try:
                url = FINVIZ_QUOTE_URL.format(ticker=ticker)
                resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                articles.extend(self._extract_ticker_news(resp.text, ticker))
            except Exception as e:
                logger.warning(f"Failed to fetch Finviz news for {ticker}: {e}")

        return articles

    def _extract_ticker_news(self, html: str, ticker: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        articles = []

        # Finviz news table has class "fullview-news-outer"
        news_table = soup.find("table", {"id": "news-table"})
        if not news_table:
            return articles

        for row in news_table.find_all("tr"):
            link = row.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not title or not url:
                continue

            # Date/time cell
            td = row.find("td")
            date_text = td.get_text(strip=True) if td else ""

            articles.append({
                "url": url,
                "title": title,
                "ticker": ticker,
                "date_text": date_text,
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

            # Prepend ticker to title for better extraction
            title = item["title"]
            ticker = item.get("ticker", "")
            if ticker and f"${ticker}" not in title and ticker not in title:
                title = f"${ticker}: {title}"

            parsed.append({
                "source": self.source_name,
                "source_url": url,
                "title": title,
                "raw_text": None,
                "published_at": datetime.now(timezone.utc),
            })

        return parsed
