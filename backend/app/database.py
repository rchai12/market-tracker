from collections.abc import AsyncGenerator
from contextlib import contextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine/session for Celery signal handlers — lazily initialised to avoid
# requiring psycopg2 at import time (tests only have asyncpg).
_sync_engine = None
_SyncSessionLocal = None


def _ensure_sync_engine():
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker

        sync_url = settings.database_url.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_url, pool_size=2, max_overflow=0)
        _SyncSessionLocal = sessionmaker(_sync_engine, class_=Session, expire_on_commit=False)


@contextmanager
def sync_session_factory():
    """Context manager for synchronous DB sessions (used in Celery signal handlers)."""
    _ensure_sync_engine()
    session = _SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
