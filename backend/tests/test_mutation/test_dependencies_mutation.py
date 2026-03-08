"""Mutation-killing tests for app/dependencies.py.

Focuses on API key prefix check, JWT type validation, inactive user rejection,
expired API key rejection, and admin check.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.dependencies import (
    _authenticate_api_key,
    _authenticate_jwt,
    get_current_admin,
)


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestApiKeyPrefix:
    def test_nonexistent_key_rejected(self):
        """Kill mutation: API key lookup returns None → UnauthorizedError."""
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        with pytest.raises(UnauthorizedError):
            _run(_authenticate_api_key("sp_nonexistent_key", db))


class TestJWTTypeCheck:
    def test_rejects_refresh_token(self):
        """Kill mutation: `type != 'access'` check removed or changed."""
        db = AsyncMock()
        with patch("app.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "1", "type": "refresh"}
            with pytest.raises(UnauthorizedError):
                _run(_authenticate_jwt("fake_token", db))

    def test_accepts_access_token(self):
        """Kill mutation: access type check works correctly."""
        db = AsyncMock()
        mock_user = MagicMock()
        mock_user.is_active = True
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_user
        db.execute.return_value = result_mock

        with patch("app.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "1", "type": "access"}
            user = _run(_authenticate_jwt("fake_token", db))
            assert user == mock_user

    def test_rejects_none_payload(self):
        """Kill mutation: `payload is None` check removed."""
        db = AsyncMock()
        with patch("app.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = None
            with pytest.raises(UnauthorizedError):
                _run(_authenticate_jwt("invalid_token", db))

    def test_rejects_missing_sub(self):
        """Kill mutation: `user_id is None` check removed."""
        db = AsyncMock()
        with patch("app.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = {"type": "access"}  # No 'sub' field
            with pytest.raises(UnauthorizedError):
                _run(_authenticate_jwt("fake_token", db))


class TestInactiveUser:
    def test_inactive_user_rejected(self):
        """Kill mutation: `not user.is_active` check removed."""
        db = AsyncMock()
        mock_user = MagicMock()
        mock_user.is_active = False
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_user
        db.execute.return_value = result_mock

        with patch("app.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "1", "type": "access"}
            with pytest.raises(UnauthorizedError):
                _run(_authenticate_jwt("fake_token", db))


class TestExpiredApiKey:
    def test_expired_key_rejected(self):
        """Kill mutation: `expires_at < now` check removed or direction reversed."""
        db = AsyncMock()
        mock_key = MagicMock()
        mock_key.is_active = True
        mock_key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_key
        db.execute.return_value = result_mock

        with patch("app.dependencies.hash_api_key") as mock_hash:
            mock_hash.return_value = "fake_hash"
            with pytest.raises(UnauthorizedError):
                _run(_authenticate_api_key("sp_expired_key", db))

    def test_inactive_key_rejected(self):
        """Kill mutation: `not api_key_obj.is_active` check removed."""
        db = AsyncMock()
        mock_key = MagicMock()
        mock_key.is_active = False
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_key
        db.execute.return_value = result_mock

        with patch("app.dependencies.hash_api_key") as mock_hash:
            mock_hash.return_value = "fake_hash"
            with pytest.raises(UnauthorizedError):
                _run(_authenticate_api_key("sp_inactive_key", db))


class TestAdminCheck:
    def test_non_admin_rejected(self):
        """Kill mutation: `not user.is_admin` check removed."""
        mock_user = MagicMock()
        mock_user.is_admin = False
        with pytest.raises(ForbiddenError):
            _run(get_current_admin(mock_user))

    def test_admin_passes(self):
        """Kill mutation: admin check rejects admins."""
        mock_user = MagicMock()
        mock_user.is_admin = True
        result = _run(get_current_admin(mock_user))
        assert result == mock_user
