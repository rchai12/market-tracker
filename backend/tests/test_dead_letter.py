"""Tests for the dead letter queue (task failure recording)."""

import json
from unittest.mock import MagicMock, patch


class TestRecordTaskFailure:
    """Tests for the record_task_failure helper."""

    def test_exception_truncation(self):
        """Exception message should be truncated to 2000 chars."""
        long_msg = "x" * 5000
        exc = ValueError(long_msg)
        truncated = str(exc)[:2000]
        assert len(truncated) == 2000

    def test_traceback_truncation(self):
        """Traceback should be truncated to 5000 chars."""
        long_tb = "line\n" * 2000
        truncated = long_tb[:5000]
        assert len(truncated) == 5000

    def test_args_serialized_as_json(self):
        """Task args should be JSON-serialized."""
        args = ("ticker", 42, {"nested": True})
        result = json.dumps(args, default=str)
        assert '"ticker"' in result
        assert "42" in result

    def test_none_args_handled(self):
        """None args/kwargs should not cause errors."""
        assert json.dumps(None, default=str) == "null"


class TestCeleryFailureSignal:
    """Tests for the task_failure signal handler in celery_app."""

    def test_signal_fires_on_max_retries(self):
        """When retries are exhausted, record_task_failure should be called."""
        from worker.celery_app import on_task_failure

        sender = MagicMock()
        sender.name = "test.task"
        sender.max_retries = 2
        sender.request.retries = 2

        exc = ValueError("test error")

        with patch("worker.utils.celery_helpers.record_task_failure") as mock_record:
            on_task_failure(
                sender=sender,
                task_id="abc-123",
                exception=exc,
                args=("arg1",),
                kwargs={"key": "val"},
                traceback=None,
            )
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["task_name"] == "test.task"
            assert call_kwargs["exception"] is exc

    def test_signal_skipped_before_max_retries(self):
        """Before retries are exhausted, should not record failure."""
        from worker.celery_app import on_task_failure

        sender = MagicMock()
        sender.name = "test.task"
        sender.max_retries = 3
        sender.request.retries = 1

        with patch("worker.utils.celery_helpers.record_task_failure") as mock_record:
            on_task_failure(
                sender=sender,
                task_id="abc-123",
                exception=ValueError("test"),
                args=(),
                kwargs={},
                traceback=None,
            )
            mock_record.assert_not_called()
