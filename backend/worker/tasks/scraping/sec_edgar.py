"""SEC EDGAR filings scraper (8-K, 10-Q, 10-K, Form 4)."""

import logging
from datetime import datetime, timezone

import httpx

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

EDGAR_FULL_TEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start}&enddt={end}&forms=8-K,10-Q,10-K,4"
EDGAR_COMPANY_FILINGS = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_RECENT_FILINGS = "https://efts.sec.gov/LATEST/search-index?forms=8-K&dateRange=custom&startdt={date}&enddt={date}"

# SEC requires identifying user agent
SEC_HEADERS = {
    "User-Agent": "StockPredictor research@example.com",
    "Accept-Encoding": "gzip, deflate",
}


class SecEdgarScraper(BaseScraper):
    source_name = "sec_edgar"

    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or []

    def scrape(self) -> list[dict]:
        articles = []

        # Use EDGAR full-text search API for recent filings
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = f"https://efts.sec.gov/LATEST/search-index?forms=8-K,10-K,10-Q&dateRange=custom&startdt={today}&enddt={today}"

        try:
            resp = httpx.get(url, headers=SEC_HEADERS, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for hit in data.get("hits", {}).get("hits", [])[:50]:
                    source = hit.get("_source", {})
                    articles.append({
                        "title": source.get("display_names", [""])[0] if source.get("display_names") else "",
                        "form_type": source.get("forms", [""])[0] if source.get("forms") else "",
                        "filing_date": source.get("file_date", ""),
                        "url": f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', '')}/{source.get('file_num', '')}",
                        "entity_name": source.get("entity_name", ""),
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch EDGAR filings: {e}")

        return articles

    def parse(self, raw_data: list[dict]) -> list[dict]:
        seen_urls = set()
        parsed = []

        for item in raw_data:
            url = item.get("url", "")
            entity_name = item.get("entity_name", "")
            form_type = item.get("form_type", "")

            if not entity_name:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = f"SEC {form_type}: {entity_name}"

            # Map form types to event categories
            event_category = None
            if form_type == "8-K":
                event_category = "material_event"
            elif form_type in ("10-Q", "10-K"):
                event_category = "earnings"
            elif form_type == "4":
                event_category = "insider_trade"

            parsed.append({
                "source": self.source_name,
                "source_url": url,
                "title": title,
                "raw_text": f"Filing type: {form_type}. Entity: {entity_name}. Date: {item.get('filing_date', '')}.",
                "published_at": datetime.now(timezone.utc),
                "metadata": {"form_type": form_type, "entity_name": entity_name},
            })

        return parsed
