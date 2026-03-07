"""MarketWatch news scraper via Dow Jones RSS feed."""

from worker.tasks.scraping.feed_scraper import FeedScraper


class MarketWatchScraper(FeedScraper):
    source_name = "marketwatch"
    feed_urls = [
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    ]
