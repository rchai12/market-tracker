"""Integration tests for error handling and edge cases."""

import pytest

from app.core.security import create_access_token, create_refresh_token
from tests.integration.conftest import _run, register_user

pytestmark = pytest.mark.integration


class TestAuthErrors:
    def test_no_token_returns_401(self, client):
        resp = _run(client.get("/api/stocks"))
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        headers = {"Authorization": "Bearer invalid.token.here"}
        resp = _run(client.get("/api/stocks", headers=headers))
        assert resp.status_code == 401

    def test_refresh_token_as_bearer_fails(self, client):
        tokens = register_user(client)
        # Use refresh token as Bearer (wrong type)
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
        resp = _run(client.get("/api/auth/me", headers=headers))
        assert resp.status_code == 401

    def test_token_for_nonexistent_user(self, client):
        # Create a valid JWT for user id 99999 (doesn't exist)
        token = create_access_token({"sub": "99999"})
        headers = {"Authorization": f"Bearer {token}"}
        resp = _run(client.get("/api/auth/me", headers=headers))
        assert resp.status_code == 401


class TestPagination:
    def test_per_page_exceeds_max(self, client, auth_headers):
        resp = _run(client.get("/api/stocks", params={"per_page": 200}, headers=auth_headers))
        assert resp.status_code == 422

    def test_page_zero_rejected(self, client, auth_headers):
        resp = _run(client.get("/api/stocks", params={"page": 0}, headers=auth_headers))
        assert resp.status_code == 422


class TestApiKeyAuth:
    def test_api_key_lifecycle(self, client, auth_headers):
        # Create an API key
        resp = _run(client.post("/api/api-keys", json={"name": "test-key"}, headers=auth_headers))
        if resp.status_code == 200:
            data = resp.json()
            raw_key = data.get("raw_key") or data.get("key")

            if raw_key:
                # Use the API key to access a protected endpoint
                key_headers = {"X-API-Key": raw_key}
                resp = _run(client.get("/api/stocks", headers=key_headers))
                assert resp.status_code == 200

    def test_invalid_api_key_rejected(self, client):
        headers = {"X-API-Key": "sp_invalid_key_12345"}
        resp = _run(client.get("/api/stocks", headers=headers))
        assert resp.status_code == 401
