"""Integration tests for signals and admin endpoints."""

import pytest

from tests.integration.conftest import _run

pytestmark = pytest.mark.integration


class TestSignals:
    def test_signals_list_empty(self, client, auth_headers):
        resp = _run(client.get("/api/signals", headers=auth_headers))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0

    def test_signals_latest_empty(self, client, auth_headers):
        resp = _run(client.get("/api/signals/latest", headers=auth_headers))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_signal_detail_not_found(self, client, auth_headers):
        resp = _run(client.get("/api/signals/detail/99999", headers=auth_headers))
        assert resp.status_code == 404

    def test_signal_accuracy_structure(self, client, auth_headers):
        resp = _run(client.get("/api/signals/accuracy", headers=auth_headers))
        assert resp.status_code == 200
        data = resp.json()
        assert "scope" in data
        assert "total_evaluated" in data

    def test_signal_accuracy_trend(self, client, auth_headers):
        resp = _run(client.get("/api/signals/accuracy/trend", headers=auth_headers))
        assert resp.status_code == 200

    def test_signals_weights(self, client, auth_headers):
        resp = _run(client.get("/api/signals/weights", headers=auth_headers))
        assert resp.status_code == 200


class TestAdmin:
    def test_db_stats_admin_only(self, client, admin_headers):
        resp = _run(client.get("/api/admin/db-stats", headers=admin_headers))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_db_stats_non_admin_rejected(self, client, auth_headers):
        resp = _run(client.get("/api/admin/db-stats", headers=auth_headers))
        assert resp.status_code == 403

    def test_admin_scrape_triggers_task(self, client, admin_headers):
        from unittest.mock import patch

        with patch("app.api.admin.orchestrate_scraping") as mock_task:
            mock_task.delay.return_value = None
            resp = _run(client.post("/api/admin/scrape-now", headers=admin_headers))
            # Accept 200 or 202 depending on implementation
            assert resp.status_code in (200, 202)
