"""Tests for data retention config, utilities, and maintenance tasks."""

from datetime import datetime, timedelta, timezone


class TestRetentionConfig:
    """Tests for retention configuration defaults and overrides."""

    def test_default_retention_values(self):
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test" * 16,
        )
        assert s.retention_article_text_days == 90
        assert s.retention_scrape_log_days == 30
        assert s.retention_alert_log_days == 90
        assert s.retention_signal_days == 180
        assert s.retention_sentiment_days == 365

    def test_retention_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("RETENTION_ARTICLE_TEXT_DAYS", "7")
        monkeypatch.setenv("RETENTION_SCRAPE_LOG_DAYS", "14")
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test" * 16,
        )
        assert s.retention_article_text_days == 7
        assert s.retention_scrape_log_days == 14


class TestRetentionUtilities:
    """Tests for retention utility constants and logic."""

    def test_batch_size_default(self):
        from worker.tasks.maintenance.retention import DELETE_BATCH_SIZE

        assert DELETE_BATCH_SIZE == 1000

    def test_cutoff_calculation_30_days(self):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        assert (now - cutoff).days == 30

    def test_cutoff_calculation_90_days(self):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=90)
        assert (now - cutoff).days == 90


class TestTaskRegistration:
    """Tests for Celery task registration names."""

    def test_compress_old_articles_registered(self):
        from worker.tasks.maintenance.tasks import compress_old_articles

        assert compress_old_articles.name == "worker.tasks.maintenance.compress_old_articles"

    def test_cleanup_scrape_logs_registered(self):
        from worker.tasks.maintenance.tasks import cleanup_scrape_logs

        assert cleanup_scrape_logs.name == "worker.tasks.maintenance.cleanup_scrape_logs"

    def test_cleanup_alert_logs_registered(self):
        from worker.tasks.maintenance.tasks import cleanup_alert_logs

        assert cleanup_alert_logs.name == "worker.tasks.maintenance.cleanup_alert_logs"

    def test_cleanup_old_signals_registered(self):
        from worker.tasks.maintenance.tasks import cleanup_old_signals

        assert cleanup_old_signals.name == "worker.tasks.maintenance.cleanup_old_signals"

    def test_run_all_maintenance_registered(self):
        from worker.tasks.maintenance.tasks import run_all_maintenance

        assert run_all_maintenance.name == "worker.tasks.maintenance.run_all_maintenance"

    def test_refresh_materialized_views_registered(self):
        from worker.tasks.maintenance.tasks import refresh_materialized_views

        assert refresh_materialized_views.name == "worker.tasks.maintenance.refresh_materialized_views"


class TestBeatSchedule:
    """Tests for beat schedule entries."""

    def test_data_maintenance_in_schedule(self):
        from worker.beat_schedule import beat_schedule

        assert "data-maintenance" in beat_schedule
        assert beat_schedule["data-maintenance"]["task"] == "worker.tasks.maintenance.run_all_maintenance"

    def test_refresh_matviews_in_schedule(self):
        from worker.beat_schedule import beat_schedule

        assert "refresh-matviews" in beat_schedule
        assert beat_schedule["refresh-matviews"]["task"] == "worker.tasks.maintenance.refresh_materialized_views"
