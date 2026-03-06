"""Tests for security hardening: secret_key validation and log sanitization."""

import pytest


class TestSecretKeyValidation:
    """Tests for production secret_key enforcement."""

    def test_insecure_default_rejected_in_production(self):
        from app.config import Settings

        with pytest.raises(ValueError, match="SECRET_KEY must be changed"):
            Settings(
                database_url="postgresql+asyncpg://test:test@localhost/test",
                secret_key="CHANGE_ME_TO_RANDOM_64_CHAR_STRING",
                environment="production",
            )

    def test_short_key_rejected_in_production(self):
        from app.config import Settings

        with pytest.raises(ValueError, match="at least 32 characters"):
            Settings(
                database_url="postgresql+asyncpg://test:test@localhost/test",
                secret_key="tooshort",
                environment="production",
            )

    def test_valid_key_accepted_in_production(self):
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="a" * 64,
            environment="production",
        )
        assert s.secret_key == "a" * 64

    def test_insecure_default_allowed_in_development(self):
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="CHANGE_ME_TO_RANDOM_64_CHAR_STRING",
            environment="development",
        )
        assert s.secret_key == "CHANGE_ME_TO_RANDOM_64_CHAR_STRING"

    def test_known_insecure_values_all_blocked(self):
        from app.config import Settings

        for insecure in ["changeme", "secret", "test"]:
            with pytest.raises(ValueError, match="SECRET_KEY must be changed"):
                Settings(
                    database_url="postgresql+asyncpg://test:test@localhost/test",
                    secret_key=insecure,
                    environment="production",
                )


class TestPasswordValidation:
    """Tests for password complexity requirements on registration."""

    def test_short_password_rejected(self):
        from app.schemas.auth import UserRegister

        with pytest.raises(ValueError, match="at least 8 characters"):
            UserRegister(email="a@b.com", username="testuser", password="Short1")

    def test_no_uppercase_rejected(self):
        from app.schemas.auth import UserRegister

        with pytest.raises(ValueError, match="uppercase"):
            UserRegister(email="a@b.com", username="testuser", password="alllower1")

    def test_no_lowercase_rejected(self):
        from app.schemas.auth import UserRegister

        with pytest.raises(ValueError, match="lowercase"):
            UserRegister(email="a@b.com", username="testuser", password="ALLUPPER1")

    def test_no_digit_rejected(self):
        from app.schemas.auth import UserRegister

        with pytest.raises(ValueError, match="digit"):
            UserRegister(email="a@b.com", username="testuser", password="NoDigitsHere")

    def test_valid_password_accepted(self):
        from app.schemas.auth import UserRegister

        user = UserRegister(email="a@b.com", username="testuser", password="ValidPass1")
        assert user.password == "ValidPass1"

    def test_short_username_rejected(self):
        from app.schemas.auth import UserRegister

        with pytest.raises(ValueError, match="3-50 characters"):
            UserRegister(email="a@b.com", username="ab", password="ValidPass1")


class TestCredentialSanitization:
    """Tests for log credential scrubbing."""

    def test_postgres_password_sanitized(self):
        from app.core.logging_config import _sanitize_credentials

        raw = "postgresql+asyncpg://sp_user:SuperSecret123@db:5432/mydb"
        result = _sanitize_credentials(raw)
        assert "SuperSecret123" not in result
        assert "sp_user:***@db" in result

    def test_redis_password_sanitized(self):
        from app.core.logging_config import _sanitize_credentials

        raw = "redis://:myredispass@redis:6379/0"
        result = _sanitize_credentials(raw)
        assert "myredispass" not in result
        assert ":***@redis" in result

    def test_no_credentials_unchanged(self):
        from app.core.logging_config import _sanitize_credentials

        raw = "Normal log message without URLs"
        assert _sanitize_credentials(raw) == raw

    def test_multiple_urls_sanitized(self):
        from app.core.logging_config import _sanitize_credentials

        raw = (
            "db=postgresql://u:pass1@host1 "
            "cache=redis://:pass2@host2"
        )
        result = _sanitize_credentials(raw)
        assert "pass1" not in result
        assert "pass2" not in result
