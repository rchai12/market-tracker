"""Phase 25a: dilution and category weights in live sentiment scoring."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from worker.tasks.signals.component_scores import (
    calc_sentiment_momentum,
    calc_sentiment_volume,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
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


def _momentum_row(
    *,
    pos: float = 0.9,
    neg: float = 0.1,
    source: str = "reuters",
    dup=None,
    stock_count: int = 1,
    event_category: str = "earnings",
):
    return SimpleNamespace(
        positive_score=pos,
        negative_score=neg,
        processed_at=NOW,
        source=source,
        duplicate_group_id=dup,
        stock_count=stock_count,
        event_category=event_category,
    )


def _volume_row(
    *,
    row_id: int,
    pos: float = 0.8,
    neg: float = 0.1,
    dup=None,
    stock_count: int = 1,
    event_category: str = "earnings",
):
    return SimpleNamespace(
        id=row_id,
        positive_score=pos,
        negative_score=neg,
        duplicate_group_id=dup,
        stock_count=stock_count,
        event_category=event_category,
    )


class TestSentimentMomentumDilution:
    def test_query_joins_associated_stock_count_and_category(self):
        session, captured = _session_capturing()
        asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        sql = _sql(captured[0])
        assert "stock_count" in sql
        assert "count(" in sql
        assert "event_category" in sql
        assert "0.7" in sql

    def test_company_specific_article_is_unaffected(self):
        row = _momentum_row(pos=0.8, neg=0.1, stock_count=1, event_category="earnings")
        session, _ = _session_capturing(rows_per_call=[[row]])
        result = asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        assert result is not None
        assert abs(result - 0.7) < 1e-9

    def test_multi_stock_article_contributes_less_than_single_stock(self):
        single_bull = _momentum_row(pos=1.0, neg=0.0, stock_count=1, event_category="earnings")
        multi_bear = _momentum_row(pos=0.0, neg=1.0, stock_count=10, event_category="earnings")
        session, _ = _session_capturing(rows_per_call=[[single_bull, multi_bear]])
        result = asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        assert result is not None
        assert result > 0  # 10-stock bearish vote is diluted vs 1-stock bullish

    def test_macro_article_discounted_vs_earnings(self):
        earnings_bull = _momentum_row(pos=1.0, neg=0.0, stock_count=1, event_category="earnings")
        macro_bear = _momentum_row(pos=0.0, neg=1.0, stock_count=1, event_category="macro")
        session, _ = _session_capturing(rows_per_call=[[earnings_bull, macro_bear]])
        result = asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        assert result is not None
        assert result > 0  # macro 0.50 vs earnings 1.0

    def test_live_macro_economic_key_also_discounted(self):
        earnings_bull = _momentum_row(pos=1.0, neg=0.0, event_category="earnings")
        macro_bear = _momentum_row(pos=0.0, neg=1.0, event_category="macro_economic")
        session, _ = _session_capturing(rows_per_call=[[earnings_bull, macro_bear]])
        result = asyncio.run(calc_sentiment_momentum(session, STOCK_ID, NOW))
        assert result is not None
        assert result > 0


class TestSentimentVolumeDilution:
    def test_volume_queries_join_stock_count(self):
        recent = [_volume_row(row_id=1)]
        session, captured = _session_capturing(rows_per_call=[recent, []])
        asyncio.run(calc_sentiment_volume(session, STOCK_ID, NOW))
        assert len(captured) == 2
        for stmt in captured:
            sql = _sql(stmt)
            assert "stock_count" in sql
            assert "event_category" in sql

    def test_multi_stock_articles_inflate_volume_less(self):
        singles = [_volume_row(row_id=i, stock_count=1, event_category="earnings") for i in range(5)]
        diluted = [_volume_row(row_id=i, stock_count=10, event_category="earnings") for i in range(5)]
        single_session, _ = _session_capturing(rows_per_call=[singles, []])
        diluted_session, _ = _session_capturing(rows_per_call=[diluted, []])
        single_score = asyncio.run(calc_sentiment_volume(single_session, STOCK_ID, NOW))
        diluted_score = asyncio.run(calc_sentiment_volume(diluted_session, STOCK_ID, NOW))
        assert single_score is not None and diluted_score is not None
        assert single_score > diluted_score > 0
