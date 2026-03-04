"""Tests for market data ingestion (mocking yfinance)."""

from unittest.mock import MagicMock, patch

import pandas as pd

from worker.tasks.scraping.market_data import _fetch_market_data_sync


class TestFetchMarketDataSync:
    def test_single_ticker(self):
        mock_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [105.0, 106.0],
                "Low": [99.0, 100.0],
                "Close": [103.0, 104.0],
                "Adj Close": [103.0, 104.0],
                "Volume": [1000000, 1100000],
            },
            index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
        )

        with patch("worker.tasks.scraping.market_data.yf") as mock_yf:
            mock_yf.download.return_value = mock_df
            result = _fetch_market_data_sync(["XOM"], period="5d")

        assert "XOM" in result
        assert len(result["XOM"]) == 2

    def test_empty_tickers(self):
        result = _fetch_market_data_sync([], period="5d")
        assert result == {}

    def test_missing_ticker_data(self):
        """When yfinance returns no data for a ticker, skip it gracefully."""
        empty_df = pd.DataFrame()

        with patch("worker.tasks.scraping.market_data.yf") as mock_yf:
            mock_yf.download.return_value = empty_df
            result = _fetch_market_data_sync(["FAKE"], period="5d")

        # Single ticker with empty data
        assert result == {}
