"""Tests for data-quality gates in component scoring queries."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from worker.tasks.signals.component_scores import (
    calc_retail_sentiment_score,
    calc_sentiment_momentum,
    calc_sentiment_volume,
    get_recent_article_count,
)
from worker.utils.article_quality import (
    QUALITY_THRESHOLD,
    SIGNAL_EXCLUDED_SOURCES,
    SIGNAL_MIN_TICKER_CONFIDENCE,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
STOCK_ID = 42


def _sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()


def _session_capturing(rows_per_call: list | None = None) -> tuple[AsyncMock, list]:
    captured: list = []
    call_idx = {"n": 0}
    session = AsyncMock()

    async def execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        if rows_per_call is None:
            result.all.return_value = []
        else:
            idx = min(call_idx["n"], len(rows_per_call) - 1)
            result.all.return_value = rows_per_call[idx]
            call_idx["n"] += 1
        return result

    session.execute = execute
    return session, captured


class TestSentimentMomentumGates:
    def test_confidence_060_excluded_from_query(self):
        session, captured = _session_capturing()
        result = asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "confidence" in sql
        assert str(SIGNAL_MIN_TICKER_CONFIDENCE) in sql or "0.7" in sql
        assert ">=" in sql
        assert result is None  # no passing rows

    def test_confidence_070_is_included_in_query(self):
        session, captured = _session_capturing()
        asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "article_stocks" in sql
        assert "0.7" in sql

    def test_reddit_excluded_returns_none_when_only_reddit_exists(self):
        session, captured = _session_capturing(rows_per_call=[[]])
        result = asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "not in" in sql
        for source in SIGNAL_EXCLUDED_SOURCES:
            assert source in sql
        assert result is None

    def test_non_canonical_articles_excluded(self):
        session, captured = _session_capturing()
        asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "canonical_article_id" in sql
        assert "is null" in sql

    def test_low_quality_score_excluded(self):
        session, captured = _session_capturing()
        asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "quality_score" in sql
        assert str(QUALITY_THRESHOLD) in sql or "0.4" in sql

    def test_null_quality_score_included_for_backward_compat(self):
        session, captured = _session_capturing()
        asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "quality_score" in sql
        assert "is null" in sql


class TestSentimentVolumeGates:
    def test_reddit_excluded_from_sentiment_volume(self):
        session, captured = _session_capturing(rows_per_call=[[], []])
        result = asyncio.run(calc_sentiment_volume(session, STOCK_ID, NOW))
        assert len(captured) >= 1
        sql_24h = _sql(captured[0])
        assert "not in" in sql_24h
        for source in SIGNAL_EXCLUDED_SOURCES:
            assert source in sql_24h
        assert result is None

    def test_both_volume_queries_apply_quality_gates(self):
        # Non-empty 24h so the baseline query also runs
        recent_row = SimpleNamespace(
            id=1, positive_score=0.8, negative_score=0.1, duplicate_group_id=None
        )
        session, captured = _session_capturing(rows_per_call=[[recent_row], []])
        asyncio.run(calc_sentiment_volume(session, STOCK_ID, NOW))
        assert len(captured) == 2
        for stmt in captured:
            sql = _sql(stmt)
            assert "confidence" in sql
            assert "not in" in sql
            assert "quality_score" in sql
            assert "canonical_article_id" in sql


class TestRecentArticleCountGates:
    def test_reddit_excluded_from_article_count(self):
        session, captured = _session_capturing(rows_per_call=[[]])
        count = asyncio.run(get_recent_article_count(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "not in" in sql
        assert count == 0


class TestRetailSentimentScore:
    def test_returns_float_when_reddit_articles_exist(self):
        row = SimpleNamespace(
            positive_score=0.8,
            negative_score=0.1,
            processed_at=NOW,
        )
        session, captured = _session_capturing(rows_per_call=[[row]])
        result = asyncio.run(calc_retail_sentiment_score(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "in (" in sql or " in(" in sql
        assert "reddit" in sql
        assert result is not None
        assert isinstance(result, float)
        assert abs(result - 0.7) < 1e-9  # 0.8 - 0.1, zero age → weight 1

    def test_returns_none_when_no_reddit_articles(self):
        session, _ = _session_capturing(rows_per_call=[[]])
        result = asyncio.run(calc_retail_sentiment_score(session, STOCK_ID, NOW))
        assert result is None
