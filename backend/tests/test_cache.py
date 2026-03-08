"""Tests for the Redis caching utility module."""

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import (
    _to_serializable,
    cache_key,
    cached,
    get_cached,
    invalidate_pattern,
    set_cached,
)


class TestCacheKey:
    """Tests for deterministic cache key generation."""

    def test_prefix_only(self):
        assert cache_key("sentiment:sectors") == "cache:sentiment:sectors"

    def test_with_params(self):
        key = cache_key("market-data:indicators", ticker="AAPL", days=365)
        expected_raw = "days=365&ticker=AAPL"
        digest = hashlib.md5(expected_raw.encode()).hexdigest()[:12]
        assert key == f"cache:market-data:indicators:{digest}"

    def test_deterministic_ordering(self):
        k1 = cache_key("test", b="2", a="1")
        k2 = cache_key("test", a="1", b="2")
        assert k1 == k2

    def test_none_params_excluded(self):
        k1 = cache_key("test", a="1", b=None)
        k2 = cache_key("test", a="1")
        assert k1 == k2

    def test_different_params_different_keys(self):
        k1 = cache_key("test", ticker="AAPL")
        k2 = cache_key("test", ticker="MSFT")
        assert k1 != k2


class TestToSerializable:
    """Tests for Pydantic model serialization helper."""

    def test_plain_dict_passthrough(self):
        data = {"a": 1, "b": "two"}
        assert _to_serializable(data) == data

    def test_list_passthrough(self):
        data = [1, 2, 3]
        assert _to_serializable(data) == [1, 2, 3]

    def test_pydantic_model_dumped(self):
        model = MagicMock()
        model.model_dump.return_value = {"field": "value"}
        result = _to_serializable(model)
        model.model_dump.assert_called_once_with(mode="json")
        assert result == {"field": "value"}

    def test_list_of_pydantic_models(self):
        m1 = MagicMock()
        m1.model_dump.return_value = {"id": 1}
        m2 = MagicMock()
        m2.model_dump.return_value = {"id": 2}
        result = _to_serializable([m1, m2])
        assert result == [{"id": 1}, {"id": 2}]


class TestGetSetCached:
    """Tests for Redis get/set operations with mocked client."""

    def test_get_cached_hit(self):
        async def _test():
            mock_client = AsyncMock()
            mock_client.get.return_value = '{"data": "cached"}'
            with patch("app.core.cache._client", return_value=mock_client):
                return await get_cached("cache:test:key")

        result = asyncio.run(_test())
        assert result == {"data": "cached"}

    def test_get_cached_miss(self):
        async def _test():
            mock_client = AsyncMock()
            mock_client.get.return_value = None
            with patch("app.core.cache._client", return_value=mock_client):
                return await get_cached("cache:test:key")

        result = asyncio.run(_test())
        assert result is None

    def test_get_cached_error_returns_none(self):
        async def _test():
            with patch("app.core.cache._client", side_effect=RuntimeError("no pool")):
                return await get_cached("cache:test:key")

        result = asyncio.run(_test())
        assert result is None

    def test_set_cached_stores_json(self):
        async def _test():
            mock_client = AsyncMock()
            with patch("app.core.cache._client", return_value=mock_client):
                await set_cached("cache:test:key", {"data": "value"}, 300)
            return mock_client

        mock_client = asyncio.run(_test())
        mock_client.set.assert_called_once()
        args = mock_client.set.call_args
        assert args[0][0] == "cache:test:key"
        assert '"data": "value"' in args[0][1]
        assert args[1]["ex"] == 300

    def test_set_cached_error_silent(self):
        async def _test():
            with patch("app.core.cache._client", side_effect=RuntimeError("no pool")):
                await set_cached("key", {"data": 1}, 300)

        asyncio.run(_test())  # Should not raise


class TestInvalidatePattern:
    """Tests for SCAN-based pattern invalidation."""

    def test_invalidate_deletes_matching_keys(self):
        async def _test():
            mock_client = AsyncMock()
            mock_client.scan.return_value = (0, ["cache:test:a", "cache:test:b"])
            mock_client.delete.return_value = 2
            with patch("app.core.cache._client", return_value=mock_client):
                return await invalidate_pattern("cache:test:*"), mock_client

        deleted, mock_client = asyncio.run(_test())
        assert deleted == 2
        mock_client.delete.assert_called_once_with("cache:test:a", "cache:test:b")

    def test_invalidate_no_matching_keys(self):
        async def _test():
            mock_client = AsyncMock()
            mock_client.scan.return_value = (0, [])
            with patch("app.core.cache._client", return_value=mock_client):
                return await invalidate_pattern("cache:nonexistent:*")

        assert asyncio.run(_test()) == 0

    def test_invalidate_error_returns_zero(self):
        async def _test():
            with patch("app.core.cache._client", side_effect=RuntimeError("no pool")):
                return await invalidate_pattern("cache:*")

        assert asyncio.run(_test()) == 0


class TestCachedDecorator:
    """Tests for the @cached() decorator factory."""

    def test_cache_miss_calls_function(self):
        async def _test():
            with patch("app.core.cache.get_cached", new_callable=AsyncMock, return_value=None) as mock_get, \
                 patch("app.core.cache.set_cached", new_callable=AsyncMock) as mock_set, \
                 patch("app.core.cache.settings") as mock_settings:
                mock_settings.cache_enabled = True
                mock_settings.cache_default_ttl = 300

                @cached("test:prefix", ttl=60)
                async def my_endpoint(ticker="AAPL"):
                    return [{"price": 100}]

                result = await my_endpoint(ticker="AAPL")
                assert result == [{"price": 100}]
                mock_get.assert_called_once()
                mock_set.assert_called_once()

        asyncio.run(_test())

    def test_cache_hit_skips_function(self):
        async def _test():
            cached_data = [{"price": 99}]
            with patch("app.core.cache.get_cached", new_callable=AsyncMock, return_value=cached_data), \
                 patch("app.core.cache.settings") as mock_settings:
                mock_settings.cache_enabled = True
                mock_settings.cache_default_ttl = 300

                call_count = 0

                @cached("test:prefix", ttl=60)
                async def my_endpoint(ticker="AAPL"):
                    nonlocal call_count
                    call_count += 1
                    return [{"price": 100}]

                result = await my_endpoint(ticker="AAPL")
                assert result == cached_data
                assert call_count == 0

        asyncio.run(_test())

    def test_cache_disabled_bypasses(self):
        async def _test():
            with patch("app.core.cache.settings") as mock_settings:
                mock_settings.cache_enabled = False

                @cached("test:prefix", ttl=60)
                async def my_endpoint():
                    return {"data": "fresh"}

                result = await my_endpoint()
                assert result == {"data": "fresh"}

        asyncio.run(_test())

    def test_di_params_excluded_from_key(self):
        async def _test():
            with patch("app.core.cache.get_cached", new_callable=AsyncMock, return_value=None) as mock_get, \
                 patch("app.core.cache.set_cached", new_callable=AsyncMock), \
                 patch("app.core.cache.settings") as mock_settings:
                mock_settings.cache_enabled = True
                mock_settings.cache_default_ttl = 300

                @cached("test:prefix", ttl=60)
                async def my_endpoint(ticker="AAPL", db=None, _user=None):
                    return []

                await my_endpoint(ticker="AAPL", db="mock_db", _user="mock_user")

                call_key = mock_get.call_args[0][0]
                expected_key = cache_key("test:prefix", ticker="AAPL")
                assert call_key == expected_key

        asyncio.run(_test())
