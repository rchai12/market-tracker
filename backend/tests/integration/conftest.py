"""Integration test fixtures.

Requires a running PostgreSQL instance. Set TEST_DATABASE_URL env var
or use the default (localhost test database).

Usage:
    TEST_DATABASE_URL=postgresql+asyncpg://sp_user:changeme@localhost:5432/sp_test \
    python -m pytest tests/integration/ -m integration
"""

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sp_user:changeme@localhost:5432/sp_test",
)

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_test_session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Session-scoped: create/drop all tables
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables at session start, drop at session end."""
    import app.models  # noqa: F401 — register all models with Base

    async def _create():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await _engine.dispose()

    try:
        _run(_create())
    except Exception as exc:
        pytest.skip(f"Test database not available: {exc}")

    yield
    _run(_drop())


# ---------------------------------------------------------------------------
# Per-test: truncate all rows for isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tables(setup_db):
    """Truncate all tables before each test for isolation."""
    async def _truncate():
        async with _engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

    _run(_truncate())
    yield


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _create_test_app():
    """Create a FastAPI app with test DB override and no-op lifespan."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from app.api.router import router
    from app.dependencies import get_db

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    app = FastAPI(lifespan=_noop_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    async def _override_get_db():
        async with _test_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    return app


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Provide an httpx AsyncClient with the test FastAPI app."""
    from unittest.mock import patch

    from app.config import settings

    with patch.object(settings, "registration_enabled", True), \
         patch.object(settings, "cache_enabled", False):
        app = _create_test_app()
        transport = ASGITransport(app=app)
        c = AsyncClient(transport=transport, base_url="http://test")
        yield c
        _run(c.aclose())


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def register_user(client, email="test@example.com", username="testuser", password="TestPass1"):
    """Register a user via the API. Returns the token response dict."""
    resp = _run(client.post("/api/auth/register", json={
        "email": email,
        "username": username,
        "password": password,
    }))
    assert resp.status_code == 200, f"Registration failed ({resp.status_code}): {resp.text}"
    return resp.json()


def login_user(client, email="test@example.com", password="TestPass1"):
    """Login via the API. Returns the token response dict."""
    resp = _run(client.post("/api/auth/login", data={
        "username": email,  # OAuth2 form uses 'username' for email
        "password": password,
    }))
    assert resp.status_code == 200, f"Login failed ({resp.status_code}): {resp.text}"
    return resp.json()


@pytest.fixture()
def auth_headers(client):
    """Register a test user and return Bearer auth headers."""
    tokens = register_user(client)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    """Create an admin user and return Bearer auth headers."""
    register_user(client, "admin@example.com", "adminuser", "AdminPass1")

    # Promote to admin via raw SQL
    async def _make_admin():
        from sqlalchemy import text
        async with _engine.begin() as conn:
            await conn.execute(
                text("UPDATE users SET is_admin = true WHERE email = 'admin@example.com'")
            )

    _run(_make_admin())

    # Re-login to get token reflecting admin status
    tokens = login_user(client, "admin@example.com", "AdminPass1")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def seed_stocks():
    """Insert test sectors and stocks directly into the test database."""
    async def _seed():
        from sqlalchemy import text
        async with _engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO sectors (id, name, is_active) VALUES (1, 'Technology', true)")
            )
            await conn.execute(text(
                "INSERT INTO stocks (ticker, company_name, sector_id, is_active) VALUES "
                "('AAPL', 'Apple Inc', 1, true), "
                "('MSFT', 'Microsoft Corporation', 1, true), "
                "('GOOGL', 'Alphabet Inc', 1, true)"
            ))

    _run(_seed())
