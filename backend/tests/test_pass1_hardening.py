"""Pass 1 ops hardening: reset, health scrub, DLQ allowlist, weekend signal skip."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from app.api.admin import LEARNING_LAYER_MODELS, LEARNING_LAYER_TABLES
from app.api.health import _check_db, _check_redis
from app.models.daily_signal_view import DailySignalViewOutcome
from worker.tasks.signals.signal_generator import _generate_signals_async
from worker.utils.celery_helpers import is_retryable_task
from worker.beat_schedule import beat_schedule

ET = ZoneInfo("America/New_York")


class TestResetLearningLayer:
    def test_includes_daily_view_outcomes(self):
        assert DailySignalViewOutcome in LEARNING_LAYER_MODELS
        assert "daily_signal_view_outcomes" in LEARNING_LAYER_TABLES

    def test_still_clears_per_signal_and_weights(self):
        names = set(LEARNING_LAYER_TABLES)
        assert names >= {
            "signal_outcomes",
            "ml_models",
            "signal_weights",
            "regime_adaptive_weights",
            "daily_signal_view_outcomes",
        }


class TestHealthErrorSanitization:
    def test_db_error_scrubs_password(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=Exception("could not connect postgresql://sp_user:SuperSecret123@db:5432/mydb")
        )
        status = asyncio.run(_check_db(session))
        assert status["status"] == "down"
        assert "SuperSecret123" not in status["error"]
        assert "sp_user:***@db" in status["error"]

    def test_redis_error_scrubs_password(self):
        with patch(
            "app.api.health.aioredis.from_url",
            side_effect=Exception("Error connecting to redis://:myredispass@redis:6379/0"),
        ):
            status = asyncio.run(_check_redis())
        assert status["status"] == "down"
        assert "myredispass" not in status["error"]
        assert ":***@redis" in status["error"]


class TestDlqRetryAllowlist:
    def test_worker_tasks_allowed(self):
        assert is_retryable_task("worker.tasks.signals.outcome_evaluator.evaluate_signal_outcomes")
        assert is_retryable_task("worker.tasks.scraping.orchestrate_scraping")

    def test_celery_builtins_rejected(self):
        assert not is_retryable_task("celery.backend_cleanup")
        assert not is_retryable_task("celery.accumulate")

    def test_empty_and_foreign_rejected(self):
        assert not is_retryable_task("")
        assert not is_retryable_task("worker.tasks.")
        assert not is_retryable_task("os.system")
        assert not is_retryable_task(None)  # type: ignore[arg-type]


class TestWeekendSignalSkip:
    def test_saturday_skips_without_db(self):
        saturday = datetime(2026, 9, 19, 16, 30, tzinfo=ET)
        with patch("worker.tasks.signals.signal_generator.async_session") as session_factory:
            result = asyncio.run(_generate_signals_async(now=saturday))
        session_factory.assert_not_called()
        assert result == {"skipped": True, "reason": "weekend"}

    def test_sunday_skips(self):
        sunday = datetime(2026, 9, 20, 12, 0, tzinfo=ET)
        result = asyncio.run(_generate_signals_async(now=sunday))
        assert result["skipped"] is True

    def test_beat_is_weekdays_only(self):
        schedule = beat_schedule["generate-signals"]["schedule"]
        assert schedule.minute == {30}
        assert schedule.day_of_week == {1, 2, 3, 4, 5}


class TestWeightCacheInvalidation:
    def test_optimizer_busts_signal_cache_after_commit(self):
        session = AsyncMock()
        query_result = MagicMock()
        query_result.scalars.return_value.all.return_value = []
        query_result.all.return_value = []
        session.execute = AsyncMock(return_value=query_result)
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "worker.tasks.signals.weight_optimizer.async_session",
                return_value=session_cm,
            ),
            patch("app.core.cache.invalidate_pattern", new_callable=AsyncMock) as mock_inv,
        ):
            from worker.tasks.signals.weight_optimizer import _compute_adaptive_weights_async

            asyncio.run(_compute_adaptive_weights_async())
            mock_inv.assert_awaited_with("cache:signals:*")
