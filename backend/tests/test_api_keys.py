"""Tests for API key generation, hashing, and authentication logic."""

import hashlib

import pytest

from app.core.security import generate_api_key, hash_api_key


class TestApiKeyGeneration:
    """Tests for API key creation."""

    def test_key_format(self):
        raw_key, key_hash, key_prefix = generate_api_key()
        assert raw_key.startswith("sp_")
        assert len(raw_key) == 67  # sp_ + 64 hex chars
        assert key_prefix == raw_key[:12]

    def test_key_hash_is_sha256(self):
        raw_key, key_hash, _ = generate_api_key()
        expected = hashlib.sha256(raw_key.encode()).hexdigest()
        assert key_hash == expected
        assert len(key_hash) == 64

    def test_unique_keys(self):
        keys = set()
        for _ in range(10):
            raw_key, _, _ = generate_api_key()
            keys.add(raw_key)
        assert len(keys) == 10

    def test_hash_consistency(self):
        raw_key = "sp_abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        h1 = hash_api_key(raw_key)
        h2 = hash_api_key(raw_key)
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        _, h1, _ = generate_api_key()
        _, h2, _ = generate_api_key()
        assert h1 != h2


class TestApiKeySchemas:
    """Tests for API key Pydantic schemas."""

    def test_create_schema_valid(self):
        from app.schemas.api_key import ApiKeyCreate

        key = ApiKeyCreate(name="My Script")
        assert key.name == "My Script"
        assert key.expires_in_days is None

    def test_create_schema_with_expiry(self):
        from app.schemas.api_key import ApiKeyCreate

        key = ApiKeyCreate(name="Temp Key", expires_in_days=30)
        assert key.expires_in_days == 30

    def test_create_schema_empty_name_rejected(self):
        from app.schemas.api_key import ApiKeyCreate

        with pytest.raises(ValueError):
            ApiKeyCreate(name="")

    def test_create_schema_long_name_rejected(self):
        from app.schemas.api_key import ApiKeyCreate

        with pytest.raises(ValueError):
            ApiKeyCreate(name="x" * 101)
