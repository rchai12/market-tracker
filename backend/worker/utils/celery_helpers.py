"""Celery task decorator factory and failure recording helpers.

Standard async Celery tasks follow a repetitive pattern:
  1. @celery_app.task(bind=True, name=..., max_retries=..., default_retry_delay=...)
  2. def task(self, ...): try: return run_async(...) except: logger.error(...); self.retry(...)

This module provides ``async_task`` which combines both into a single decorator,
and ``record_task_failure`` for the dead letter queue.
"""

import functools
import json
import logging
import traceback as tb_module

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


def record_task_failure(
    task_name: str,
    args: tuple | None = None,
    kwargs: dict | None = None,
    exception: BaseException | None = None,
    traceback_str: str | None = None,
) -> None:
    """Record a task failure to the task_failures table (dead letter queue).

    Called from the Celery ``task_failure`` signal when retries are exhausted.
    Uses a synchronous DB connection to avoid async complications in signal handlers.
    """
    try:
        from app.database import sync_session_factory
        from app.models.task_failure import TaskFailure

        exc_type = type(exception).__name__ if exception else None
        exc_msg = str(exception)[:2000] if exception else None
        tb_text = traceback_str[:5000] if traceback_str else None

        with sync_session_factory() as session:
            failure = TaskFailure(
                task_name=task_name,
                task_args=json.dumps(args, default=str)[:2000] if args else None,
                task_kwargs=json.dumps(kwargs, default=str)[:2000] if kwargs else None,
                exception_type=exc_type,
                exception_message=exc_msg,
                traceback=tb_text,
                retries_exhausted=True,
            )
            session.add(failure)
            session.commit()
            logger.info("Recorded task failure for %s (id=%d)", task_name, failure.id)
    except Exception:
        logger.error("Failed to record task failure for %s", task_name, exc_info=True)
