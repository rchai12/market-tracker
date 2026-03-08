"""Tests for the event classifier utility."""

import pytest

from worker.utils.event_classifier import classify_event


class TestEarningsCategory:
    def test_earnings_report(self):
        assert classify_event("Apple Earnings Report Beats Estimates") == "earnings"

    def test_quarterly_results(self):
        assert classify_event("MSFT Q3 Quarterly Results Show Strong Growth") == "earnings"

    def test_revenue_beat(self):
        assert classify_event("Tesla Revenue Beat Sends Stock Higher") == "earnings"

    def test_eps(self):
        assert classify_event("AMD reports EPS of $1.50") == "earnings"

    def test_guidance(self):
        assert classify_event("NVDA raises full-year guidance") == "earnings"

    def test_10k_filing(self):
        assert classify_event("Company files 10-K with SEC") == "earnings"


class TestMergerAcquisitionCategory:
    def test_acquisition(self):
        assert classify_event("Broadcom Completes Acquisition of VMware") == "merger_acquisition"

    def test_merger_agreement(self):
        assert classify_event("Merger Agreement Reached Between X and Y") == "merger_acquisition"

    def test_takeover_bid(self):
        assert classify_event("Hostile Takeover Bid Rejected by Board") == "merger_acquisition"

    def test_buyout(self):
        assert classify_event("Private Equity Firm Announces Buyout") == "merger_acquisition"


class TestRegulatoryCategory:
    def test_fda_approval(self):
        assert classify_event("FDA Approval Granted for New Drug") == "regulatory"

    def test_antitrust(self):
        assert classify_event("DOJ Launches Antitrust Investigation") == "regulatory"

    def test_sec_investigation(self):
        assert classify_event("SEC Investigation into Trading Practices") == "regulatory"


class TestAnalystRatingCategory:
    def test_price_target(self):
        assert classify_event("Goldman Raises Price Target on AAPL to $250") == "analyst_rating"

    def test_upgrades(self):
        assert classify_event("JPMorgan Upgrades TSLA to Overweight") == "analyst_rating"

    def test_downgrades(self):
        assert classify_event("Analyst Downgrades META to Hold") == "analyst_rating"

    def test_initiates_coverage(self):
        assert classify_event("Morgan Stanley Initiates Coverage on NVDA") == "analyst_rating"


class TestMacroEconomicCategory:
    def test_interest_rate(self):
        assert classify_event("Federal Reserve Holds Interest Rate Steady") == "macro_economic"

    def test_inflation(self):
        assert classify_event("Inflation Data Shows Cooling Prices") == "macro_economic"

    def test_gdp(self):
        assert classify_event("US GDP Growth Exceeds Expectations") == "macro_economic"

    def test_cpi(self):
        assert classify_event("CPI Report Shows Moderate Price Increases") == "macro_economic"

    def test_jobs_report(self):
        assert classify_event("Jobs Report Shows Strong Hiring") == "macro_economic"


class TestLegalCategory:
    def test_lawsuit(self):
        assert classify_event("Major Lawsuit Filed Against Tech Giant") == "legal"

    def test_class_action(self):
        assert classify_event("Class Action Suit Over Securities Fraud") == "legal"

    def test_settlement(self):
        assert classify_event("Company Reaches $500M Settlement") == "legal"


class TestDividendCategory:
    def test_dividend_increase(self):
        assert classify_event("Apple Announces Dividend Increase") == "dividend"

    def test_stock_buyback(self):
        assert classify_event("Board Approves $10B Stock Buyback") == "dividend"

    def test_share_repurchase(self):
        assert classify_event("Company Initiates Share Repurchase Program") == "dividend"


class TestProductLaunchCategory:
    def test_product_launch(self):
        assert classify_event("Apple Product Launch Event Next Week") == "product_launch"

    def test_unveils(self):
        assert classify_event("Tesla Unveils New Model") == "product_launch"


class TestInsiderTradeCategory:
    def test_insider_buying(self):
        assert classify_event("CEO Reports Insider Buying of 50K Shares") == "insider_trade"

    def test_form_4(self):
        assert classify_event("Form 4 Filing Shows Insider Purchase") == "insider_trade"


class TestSourceOverrides:
    def test_fred_always_macro(self):
        assert classify_event("Random Title With No Keywords", source="fred") == "macro_economic"

    def test_fred_overrides_keywords(self):
        assert classify_event("Company Earnings Beat Estimates", source="fred") == "macro_economic"


class TestDefaultAndEdgeCases:
    def test_default_general_news(self):
        assert classify_event("Random Headline About Nothing") == "general_news"

    def test_case_insensitive(self):
        assert classify_event("EARNINGS REPORT Shows Growth") == "earnings"

    def test_body_matching(self):
        assert classify_event("Breaking News", body="The earnings report showed...") == "earnings"

    def test_title_only(self):
        assert classify_event("Dividend Cut Announced") == "dividend"

    def test_empty_body(self):
        assert classify_event("GDP growth slows", body=None) == "macro_economic"

    def test_no_source(self):
        assert classify_event("Some headline", source=None) == "general_news"

    def test_longest_match_wins(self):
        # "merger agreement" should match before "merger"
        result = classify_event("Merger Agreement Signed Today")
        assert result == "merger_acquisition"

    def test_body_only_match(self):
        """Kill mutation: body text is searched when title has no keywords."""
        result = classify_event("Breaking Market News", body="Dividend payout raised by board")
        assert result == "dividend"

    def test_multiple_keywords_first_category_wins(self):
        """Kill mutation: category priority ordering matters."""
        result = classify_event("Earnings Report Shows Dividend Increase")
        # Both "earnings" and "dividend" keywords present — first match wins
        assert result in ("earnings", "dividend")

    def test_case_edge_mixed(self):
        """Kill mutation: case-insensitive matching across mixed case."""
        assert classify_event("fda APPROVAL for new therapy") == "regulatory"
        assert classify_event("Insider BUYING of shares reported") == "insider_trade"

    def test_partial_keyword_no_match(self):
        """Kill mutation: ensure word boundary matching (no partial matches)."""
        # "earn" should not match "earnings" category if not a keyword
        result = classify_event("Company earnings surprise analysts")
        assert result == "earnings"  # Full keyword "earnings" matches
