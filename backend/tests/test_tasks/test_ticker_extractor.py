"""Tests for ticker extraction utility."""

from worker.utils.ticker_extractor import extract_tickers

KNOWN_TICKERS = {"XOM", "CVX", "JPM", "AAPL", "MSFT", "BAC", "GS", "V"}


class TestTickerExtractor:
    def test_dollar_sign_tickers(self):
        title = "Breaking: $XOM reports record earnings"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 1
        assert results[0] == ("XOM", 0.95)

    def test_multiple_dollar_tickers(self):
        title = "$XOM and $CVX lead energy sector rally"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        tickers = {r[0] for r in results}
        assert "XOM" in tickers
        assert "CVX" in tickers

    def test_caps_word_matching(self):
        title = "JPM beats earnings expectations this quarter"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 1
        assert results[0][0] == "JPM"
        assert results[0][1] == 0.70

    def test_excludes_common_words(self):
        title = "CEO of company says GDP growth will affect SEC filings"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 0

    def test_unknown_ticker_ignored(self):
        title = "$FAKE ticker mentioned"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 0

    def test_body_text_included(self):
        title = "Energy sector news"
        body = "Investors are watching $GS closely after the merger announcement."
        results = extract_tickers(title, body, KNOWN_TICKERS)
        assert len(results) == 1
        assert results[0][0] == "GS"

    def test_dollar_sign_higher_confidence_than_caps(self):
        title = "$XOM XOM mentioned twice"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 1
        assert results[0] == ("XOM", 0.95)  # takes highest confidence

    def test_sorted_by_confidence_desc(self):
        title = "$XOM is up but BAC is also rising"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert results[0][1] >= results[-1][1]
