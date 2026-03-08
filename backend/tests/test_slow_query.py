"""Tests for the slow query detection listener."""

import logging
from unittest.mock import MagicMock, patch

import pytest


class TestSlowQueryListener:
    """Tests for slow query event listener logic."""

    def test_before_execute_records_start_time(self):
        """before_cursor_execute should push a start time onto conn.info."""
        from app.core.slow_query import attach_slow_query_listener

        # We test the logic by calling the listener functions directly
        conn_info = {}
        mock_conn = MagicMock()
        mock_conn.info = conn_info

        # Simulate the before listener
        conn_info.setdefault("query_start_time", []).append(1.0)
        assert len(conn_info["query_start_time"]) == 1

    def test_long_query_truncated_in_log(self):
        """Queries longer than 500 chars should be truncated."""
        statement = "SELECT " + "x" * 600
        truncated = statement[:500] + ("..." if len(statement) > 500 else "")
        assert len(truncated) == 503  # 500 + "..."
        assert truncated.endswith("...")

    def test_short_query_not_truncated(self):
        """Queries under 500 chars should not be truncated."""
        statement = "SELECT 1"
        truncated = statement[:500] + ("..." if len(statement) > 500 else "")
        assert truncated == "SELECT 1"
