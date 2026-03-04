"""Tests for scraper parse() methods (no network calls)."""

from datetime import datetime, timezone

from worker.tasks.scraping.fred import FredScraper
from worker.tasks.scraping.reuters_rss import ReutersRssScraper
from worker.tasks.scraping.sec_edgar import SecEdgarScraper
from worker.tasks.scraping.yahoo_news import YahooNewsScraper


class TestYahooNewsScraper:
    def test_parse_deduplicates_urls(self):
        scraper = YahooNewsScraper()
        raw = [
            {"url": "https://finance.yahoo.com/news/article-1", "title": "Apple earnings beat"},
            {"url": "https://finance.yahoo.com/news/article-1", "title": "Apple earnings beat"},
            {"url": "https://finance.yahoo.com/news/article-2", "title": "Tech rally continues"},
        ]
        result = scraper.parse(raw)
        assert len(result) == 2
        urls = {r["source_url"] for r in result}
        assert len(urls) == 2

    def test_parse_sets_source(self):
        scraper = YahooNewsScraper()
        raw = [{"url": "https://finance.yahoo.com/news/test", "title": "Test article"}]
        result = scraper.parse(raw)
        assert result[0]["source"] == "yahoo_finance"

    def test_parse_empty_input(self):
        scraper = YahooNewsScraper()
        assert scraper.parse([]) == []

    def test_extract_articles_from_html(self):
        scraper = YahooNewsScraper()
        html = """
        <html><body>
            <a href="/news/stock-market-rally-123"><h3>Stock Market Rally Pushes Higher Today</h3></a>
            <a href="/news/fed-decision-456"><h3>Fed Decision Coming This Week Ahead</h3></a>
            <a href="/about"><h3>About Yahoo Finance Page</h3></a>
        </body></html>
        """
        articles = scraper._extract_articles(html)
        # Only /news/ links with titles >= 15 chars
        assert len(articles) == 2
        assert articles[0]["title"] == "Stock Market Rally Pushes Higher Today"


class TestReutersRssScraper:
    def test_parse_deduplicates(self):
        scraper = ReutersRssScraper()
        raw = [
            {"url": "https://reuters.com/1", "title": "Markets rally", "summary": "...", "published": "", "author": ""},
            {"url": "https://reuters.com/1", "title": "Markets rally", "summary": "...", "published": "", "author": ""},
        ]
        result = scraper.parse(raw)
        assert len(result) == 1

    def test_parse_skips_empty_title(self):
        scraper = ReutersRssScraper()
        raw = [
            {"url": "https://reuters.com/1", "title": "", "summary": "...", "published": "", "author": ""},
        ]
        result = scraper.parse(raw)
        assert len(result) == 0

    def test_parse_sets_source(self):
        scraper = ReutersRssScraper()
        raw = [
            {"url": "https://reuters.com/1", "title": "Test", "summary": "Body", "published": "", "author": "John"},
        ]
        result = scraper.parse(raw)
        assert result[0]["source"] == "reuters"
        assert result[0]["author"] == "John"


class TestSecEdgarScraper:
    def test_parse_sets_event_category(self):
        scraper = SecEdgarScraper()
        raw = [
            {"url": "https://sec.gov/1", "entity_name": "Apple Inc", "form_type": "8-K", "filing_date": "2025-01-01"},
            {"url": "https://sec.gov/2", "entity_name": "Microsoft", "form_type": "10-Q", "filing_date": "2025-01-01"},
            {"url": "https://sec.gov/3", "entity_name": "Google", "form_type": "4", "filing_date": "2025-01-01"},
        ]
        result = scraper.parse(raw)
        assert result[0]["title"] == "SEC 8-K: Apple Inc"
        assert result[1]["title"] == "SEC 10-Q: Microsoft"

    def test_parse_skips_no_entity(self):
        scraper = SecEdgarScraper()
        raw = [
            {"url": "https://sec.gov/1", "entity_name": "", "form_type": "8-K", "filing_date": ""},
        ]
        result = scraper.parse(raw)
        assert len(result) == 0

    def test_parse_deduplicates(self):
        scraper = SecEdgarScraper()
        raw = [
            {"url": "https://sec.gov/1", "entity_name": "Apple", "form_type": "8-K", "filing_date": ""},
            {"url": "https://sec.gov/1", "entity_name": "Apple", "form_type": "8-K", "filing_date": ""},
        ]
        result = scraper.parse(raw)
        assert len(result) == 1


class TestFredScraper:
    def test_parse_deduplicates(self):
        scraper = FredScraper()
        raw = [
            {"release_name": "CPI", "date": "2025-01-01", "release_id": 10},
            {"release_name": "CPI", "date": "2025-01-01", "release_id": 10},
            {"release_name": "GDP", "date": "2025-01-01", "release_id": 20},
        ]
        result = scraper.parse(raw)
        assert len(result) == 2

    def test_parse_skips_empty_name(self):
        scraper = FredScraper()
        raw = [{"release_name": "", "date": "2025-01-01", "release_id": 10}]
        result = scraper.parse(raw)
        assert len(result) == 0

    def test_parse_format(self):
        scraper = FredScraper()
        raw = [{"release_name": "Unemployment Rate", "date": "2025-06-01", "release_id": 50}]
        result = scraper.parse(raw)
        assert result[0]["source"] == "fred"
        assert "Unemployment Rate" in result[0]["title"]
        assert "2025-06-01" in result[0]["title"]
        assert result[0]["source_url"] == "https://fred.stlouisfed.org/releases/50"
