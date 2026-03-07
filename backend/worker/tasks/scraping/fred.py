"""FRED economic indicator scraper."""

import logging
from datetime import datetime, timezone

import httpx

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Key economic series to track
FRED_SERIES = {
    "CPIAUCSL": "Consumer Price Index (CPI)",
    "UNRATE": "Unemployment Rate",
    "FEDFUNDS": "Federal Funds Rate",
    "GDP": "Gross Domestic Product",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "VIXCLS": "VIX Volatility Index",
}

FRED_RELEASES_URL = "https://api.stlouisfed.org/fred/releases/dates"
FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredScraper(BaseScraper):
    source_name = "fred"

    def scrape(self) -> list[dict]:
        """Fetch recent FRED releases and economic data points."""
        from app.config import settings

        articles = []

        if not settings.fred_api_key:
            logger.warning("FRED API key not configured (FRED_API_KEY), skipping")
            return articles

        try:
            resp = httpx.get(
                "https://api.stlouisfed.org/fred/releases/dates",
                params={
                    "api_key": settings.fred_api_key,
                    "file_type": "json",
                    "limit": 20,
                    "sort_order": "desc",
                    "include_release_dates_with_no_data": "false",
                },
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                for release in data.get("release_dates", []):
                    articles.append({
                        "release_id": release.get("release_id"),
                        "release_name": release.get("release_name", ""),
                        "date": release.get("date", ""),
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch FRED releases: {e}")

        return articles

    def parse(self, raw_data: list[dict]) -> list[dict]:
        seen = set()
        parsed = []

        for item in raw_data:
            release_name = item.get("release_name", "")
            release_date = item.get("date", "")

            key = f"{release_name}_{release_date}"
            if key in seen or not release_name:
                continue
            seen.add(key)

            parsed.append({
                "source": self.source_name,
                "source_url": f"https://fred.stlouisfed.org/releases/{item.get('release_id', '')}",
                "title": f"FRED: {release_name} ({release_date})",
                "raw_text": f"Economic data release: {release_name}. Date: {release_date}.",
                "published_at": datetime.now(timezone.utc),
                "metadata": {
                    "release_id": item.get("release_id"),
                    "release_name": release_name,
                    "release_date": release_date,
                },
            })

        return parsed
