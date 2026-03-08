"""Integration tests for the authentication flow.

Exercises: register → login → refresh → /me → profile update → password change.
"""

import pytest

from tests.integration.conftest import _run, login_user, register_user

pytestmark = pytest.mark.integration


class TestRegister:
    def test_register_success(self, client):
        data = register_user(client)
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["username"] == "testuser"
        assert data["user"]["is_admin"] is False

    def test_register_duplicate_email(self, client):
        register_user(client)
        resp = _run(client.post("/api/auth/register", json={
            "email": "test@example.com",
            "username": "otheruser",
            "password": "TestPass1",
        }))
        assert resp.status_code == 409

    def test_register_weak_password(self, client):
        resp = _run(client.post("/api/auth/register", json={
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "short",
        }))
        assert resp.status_code == 422

    def test_register_short_username(self, client):
        resp = _run(client.post("/api/auth/register", json={
            "email": "short@example.com",
            "username": "ab",
            "password": "TestPass1",
        }))
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        register_user(client)
        data = login_user(client)
        assert data["access_token"]
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, client):
        register_user(client)
        resp = _run(client.post("/api/auth/login", data={
            "username": "test@example.com",
            "password": "WrongPass1",
        }))
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client):
        resp = _run(client.post("/api/auth/login", data={
            "username": "nobody@example.com",
            "password": "TestPass1",
        }))
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_token(self, client):
        tokens = register_user(client)
        resp = _run(client.post("/api/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        }))
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["access_token"] != tokens["access_token"]

    def test_refresh_with_access_token_fails(self, client):
        tokens = register_user(client)
        resp = _run(client.post("/api/auth/refresh", json={
            "refresh_token": tokens["access_token"],  # Wrong token type
        }))
        assert resp.status_code == 401


class TestMeAndProfile:
    def test_get_me(self, client, auth_headers):
        resp = _run(client.get("/api/auth/me", headers=auth_headers))
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    def test_update_profile(self, client, auth_headers):
        resp = _run(client.put("/api/auth/profile", json={
            "username": "newname",
        }, headers=auth_headers))
        assert resp.status_code == 200
        assert resp.json()["username"] == "newname"

    def test_change_password(self, client, auth_headers):
        resp = _run(client.put("/api/auth/password", json={
            "current_password": "TestPass1",
            "new_password": "NewPass99",
        }, headers=auth_headers))
        assert resp.status_code == 200

        # Verify new password works
        data = login_user(client, password="NewPass99")
        assert data["access_token"]
