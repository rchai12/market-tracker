"""Celery task decorator factory to reduce boilerplate.

Standard async Celery tasks follow a repetitive pattern:
  1. @celery_app.task(bind=True, name=..., max_retries=..., default_retry_delay=...)
  2. def task(self, ...): try: return run_async(...) except: logger.error(...); self.retry(...)

This module provides ``async_task`` which combines both into a single decorator.
"""

import functools
import logging

from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


def async_task(
    name: str,
    *,
    max_retries: int = 2,
    retry_delay: int = 60,
    **task_kwargs,
):
    """Decorator factory for async Celery tasks with standard retry logic.

    Usage::

        @async_task("worker.tasks.maintenance.compress_old_articles", max_retries=1, retry_delay=120)
        async def compress_old_articles():
            ...
            return {"compressed": count}

    This replaces the pattern of a sync wrapper + separate async function.
    The decorated function becomes the Celery task directly.
    """

    def decorator(async_fn):
        short_name = name.rsplit(".", 1)[-1]

        @celery_app.task(
            name=name,
            bind=True,
            max_retries=max_retries,
            default_retry_delay=retry_delay,
            **task_kwargs,
        )
        @functools.wraps(async_fn)
        def wrapper(self, *args, **kwargs):
            try:
                return run_async(async_fn(*args, **kwargs))
            except Exception as exc:
                logger.error("%s failed: %s", short_name, exc)
                if max_retries > 0:
                    raise self.retry(exc=exc)
                raise

        return wrapper

    return decorator
