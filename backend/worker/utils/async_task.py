"""Utility for running async coroutines from synchronous Celery tasks."""

import asyncio
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: asyncio.coroutines) -> T:
    """Run an async coroutine in a new event loop.

    Used by Celery tasks that need to call async database code.
    Creates a fresh event loop, runs the coroutine, and cleans up.
    Disposes the async engine pool to prevent stale connections
    from being reused across different event loops.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        from app.database import engine

        loop.run_until_complete(engine.dispose())
        loop.close()
