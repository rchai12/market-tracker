"""Google News RSS scraper for financial news."""

from worker.tasks.scraping.feed_scraper import FeedScraper


class GoogleNewsScraper(FeedScraper):
    source_name = "google_news"
    feed_urls = [
        "https://news.google.com/rss/search?q=stock+market+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=earnings+report+when:1d&hl=en-US&gl=US&ceid=US:en",
    ]

    def _build_metadata(self, item: dict) -> dict | None:
        source_detail = item.get("source_detail", {})
        original_source = source_detail.get("title", "") if isinstance(source_detail, dict) else ""
        if original_source:
            return {"original_source": original_source}
        return None
