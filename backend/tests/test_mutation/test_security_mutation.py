"""Mutation-killing tests for app/core/security.py.

Focuses on token type fields, API key prefix/length, hash determinism.
"""

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_api_key,
)


class TestTokenType:
    def test_access_token_has_access_type(self):
        """Kill mutation: `type: 'access'` changed to `type: 'refresh'`."""
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"

    def test_refresh_token_has_refresh_type(self):
        """Kill mutation: `type: 'refresh'` changed to `type: 'access'`."""
        token = create_refresh_token({"sub": "1"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_access_and_refresh_types_differ(self):
        """Kill mutation: both types set to same value."""
        access = create_access_token({"sub": "1"})
        refresh = create_refresh_token({"sub": "1"})
        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)
        assert access_payload["type"] != refresh_payload["type"]


class TestApiKeyGeneration:
    def test_prefix_sp_underscore(self):
        """Kill mutation: `'sp_'` prefix changed."""
        raw_key, key_hash, key_prefix = generate_api_key()
        assert raw_key.startswith("sp_")

    def test_key_prefix_length_12(self):
        """Kill mutation: `[:12]` slice changed."""
        raw_key, key_hash, key_prefix = generate_api_key()
        assert len(key_prefix) == 12
        assert key_prefix == raw_key[:12]

    def test_key_uniqueness(self):
        """Kill mutation: random generation produces unique keys."""
        key1 = generate_api_key()[0]
        key2 = generate_api_key()[0]
        assert key1 != key2


class TestApiKeyHashing:
    def test_hash_deterministic(self):
        """Kill mutation: hash function produces consistent results."""
        raw_key = "sp_abc123def456"
        hash1 = hash_api_key(raw_key)
        hash2 = hash_api_key(raw_key)
        assert hash1 == hash2

    def test_hash_differs_for_different_keys(self):
        """Kill mutation: hash function ignores input."""
        hash1 = hash_api_key("sp_key_one")
        hash2 = hash_api_key("sp_key_two")
        assert hash1 != hash2

    def test_generated_key_hash_matches(self):
        """Kill mutation: `hash_api_key(raw_key)` called correctly in generate."""
        raw_key, key_hash, _ = generate_api_key()
        assert hash_api_key(raw_key) == key_hash
