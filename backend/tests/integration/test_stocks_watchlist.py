"""Integration tests for stocks and watchlist endpoints."""

import pytest

from tests.integration.conftest import _run

pytestmark = pytest.mark.integration


class TestStocks:
    def test_list_stocks_empty(self, client, auth_headers):
        resp = _run(client.get("/api/stocks", headers=auth_headers))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0

    def test_list_stocks_with_data(self, client, auth_headers, seed_stocks):
        resp = _run(client.get("/api/stocks", headers=auth_headers))
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] == 3
        tickers = {s["ticker"] for s in data["data"]}
        assert tickers == {"AAPL", "MSFT", "GOOGL"}

    def test_stock_detail(self, client, auth_headers, seed_stocks):
        resp = _run(client.get("/api/stocks/AAPL", headers=auth_headers))
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"
        assert resp.json()["company_name"] == "Apple Inc"

    def test_stock_detail_not_found(self, client, auth_headers):
        resp = _run(client.get("/api/stocks/FAKE", headers=auth_headers))
        assert resp.status_code == 404

    def test_sectors_endpoint(self, client, auth_headers, seed_stocks):
        resp = _run(client.get("/api/stocks/sectors", headers=auth_headers))
        assert resp.status_code == 200
        sectors = resp.json()
        assert any(s["name"] == "Technology" for s in sectors)

    def test_stock_search(self, client, auth_headers, seed_stocks):
        resp = _run(client.get("/api/stocks", params={"search": "apple"}, headers=auth_headers))
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] == 1
        assert data["data"][0]["ticker"] == "AAPL"


class TestWatchlist:
    def test_watchlist_add_and_list(self, client, auth_headers, seed_stocks):
        # Add
        resp = _run(client.post("/api/watchlist", json={"ticker": "AAPL"}, headers=auth_headers))
        assert resp.status_code == 201

        # List
        resp = _run(client.get("/api/watchlist", headers=auth_headers))
        assert resp.status_code == 200
        tickers = [item["ticker"] for item in resp.json()]
        assert "AAPL" in tickers

    def test_watchlist_remove(self, client, auth_headers, seed_stocks):
        _run(client.post("/api/watchlist", json={"ticker": "MSFT"}, headers=auth_headers))
        resp = _run(client.delete("/api/watchlist/MSFT", headers=auth_headers))
        assert resp.status_code == 204

        # Verify removed
        resp = _run(client.get("/api/watchlist", headers=auth_headers))
        tickers = [item["ticker"] for item in resp.json()]
        assert "MSFT" not in tickers
