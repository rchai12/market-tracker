"""Tests for ticker extraction utility."""

from worker.utils.ticker_extractor import build_company_map, extract_tickers

KNOWN_TICKERS = {"XOM", "CVX", "JPM", "AAPL", "MSFT", "BAC", "GS", "V", "ORCL", "TSLA"}

COMPANY_NAMES = [
    ("XOM", "Exxon Mobil Corporation"),
    ("AAPL", "Apple Inc"),
    ("MSFT", "Microsoft Corporation"),
    ("ORCL", "Oracle Corporation"),
    ("TSLA", "Tesla Inc"),
    ("JPM", "JPMorgan Chase & Co"),
    ("GS", "Goldman Sachs Group Inc"),
]

COMPANY_MAP = build_company_map(COMPANY_NAMES)


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


class TestParentheticalTickers:
    def test_parenthetical_ticker(self):
        title = "Down 24% in 2026, Should You Buy the Dip in Oracle (ORCL) Stock?"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        tickers = {r[0] for r in results}
        assert "ORCL" in tickers

    def test_parenthetical_confidence(self):
        title = "MercadoLibre (AAPL) reports earnings"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert results[0] == ("AAPL", 0.90)

    def test_parenthetical_unknown_ticker(self):
        title = "Netskope (NTSK) Exceeds Consensus"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 0


class TestCompanyNameMatching:
    def test_company_name_in_title(self):
        title = "Down 24% in 2026, Should You Buy the Dip in Oracle Stock?"
        results = extract_tickers(title, None, KNOWN_TICKERS, company_map=COMPANY_MAP)
        tickers = {r[0] for r in results}
        assert "ORCL" in tickers

    def test_company_name_confidence(self):
        title = "Oracle reports strong quarterly earnings"
        results = extract_tickers(title, None, KNOWN_TICKERS, company_map=COMPANY_MAP)
        assert ("ORCL", 0.60) in results

    def test_company_name_case_insensitive(self):
        title = "tesla surges on delivery numbers"
        results = extract_tickers(title, None, KNOWN_TICKERS, company_map=COMPANY_MAP)
        tickers = {r[0] for r in results}
        assert "TSLA" in tickers

    def test_multiple_company_names(self):
        title = "Apple and Microsoft lead tech rally"
        results = extract_tickers(title, None, KNOWN_TICKERS, company_map=COMPANY_MAP)
        tickers = {r[0] for r in results}
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_no_company_map_backward_compatible(self):
        title = "Oracle reports earnings"
        results = extract_tickers(title, None, KNOWN_TICKERS)
        assert len(results) == 0  # no match without company_map

    def test_company_name_in_body(self):
        title = "Tech sector news"
        body = "Investors are watching Tesla closely after the delivery report."
        results = extract_tickers(title, body, KNOWN_TICKERS, company_map=COMPANY_MAP)
        tickers = {r[0] for r in results}
        assert "TSLA" in tickers


class TestBuildCompanyMap:
    def test_builds_short_names(self):
        m = build_company_map([("AAPL", "Apple Inc")])
        assert "Apple Inc" in m
        assert "Apple" in m
        assert m["Apple"] == "AAPL"

    def test_strips_corporation(self):
        m = build_company_map([("ORCL", "Oracle Corporation")])
        assert "Oracle" in m
        assert m["Oracle"] == "ORCL"

    def test_multi_word_short_name(self):
        m = build_company_map([("XOM", "Exxon Mobil Corporation")])
        assert "Exxon Mobil" in m
        assert m["Exxon Mobil"] == "XOM"
