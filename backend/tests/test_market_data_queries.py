"""Shared daily OHLCV lookups and learning-loop DB loaders."""

import asyncio
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from worker.utils.daily_aggregation import MIN_CONVICTION
from worker.utils.learning_queries import fetch_learning_view_outcomes, load_signals_for_views
from worker.utils.market_data_queries import (
    close_on_or_before,
    latest_close,
    latest_closes,
    nth_trading_day_close,
    recent_close_volume,
    recent_closes,
)


def _sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()


def _session_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _session_capturing(result: MagicMock | None = None) -> tuple[AsyncMock, list]:
    captured: list = []
    session = AsyncMock()

    async def execute(stmt):
        captured.append(stmt)
        return result or MagicMock()

    session.execute = execute
    return session, captured


class TestCloseLookups:
    def test_close_on_or_before_returns_float(self):
        session = _session_scalar(101.5)
        price = asyncio.run(close_on_or_before(session, 1, date(2026, 9, 14)))
        assert price == 101.5

    def test_close_on_or_before_missing(self):
        session = _session_scalar(None)
        assert asyncio.run(close_on_or_before(session, 1, date(2026, 9, 14))) is None

    def test_nth_trading_day_close(self):
        session = _session_scalar(110.0)
        price = asyncio.run(nth_trading_day_close(session, 1, date(2026, 9, 14), 3))
        assert price == 110.0

    def test_latest_close_none_stock_skips_query(self):
        session = AsyncMock()
        assert asyncio.run(latest_close(session, None)) is None
        session.execute.assert_not_called()

    def test_latest_closes_empty_skips_query(self):
        session = AsyncMock()
        assert asyncio.run(latest_closes(session, [])) == {}
        assert asyncio.run(latest_closes(session, [None])) == {}
        session.execute.assert_not_called()

    def test_latest_closes_batches(self):
        result = MagicMock()
        result.all.return_value = [(10, 50.0), (11, 75.25)]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        out = asyncio.run(latest_closes(session, [10, 11, 10]))
        assert out == {10: 50.0, 11: 75.25}
        session.execute.assert_awaited_once()

    def test_recent_closes_oldest_first(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [3.0, 2.0, 1.0]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        assert asyncio.run(recent_closes(session, 1, 3)) == [1.0, 2.0, 3.0]

    def test_recent_close_volume_oldest_first(self):
        result = MagicMock()
        result.all.return_value = [
            SimpleNamespace(close=3.0, volume=300.0),
            SimpleNamespace(close=2.0, volume=200.0),
        ]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        closes, volumes = asyncio.run(recent_close_volume(session, 1, 2))
        assert closes == [2.0, 3.0]
        assert volumes == [200.0, 300.0]

    def test_recent_close_volume_missing_values_are_zero(self):
        result = MagicMock()
        result.all.return_value = [SimpleNamespace(close=None, volume=None)]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        closes, volumes = asyncio.run(recent_close_volume(session, 1, 1))
        assert closes == [0.0]
        assert volumes == [0.0]

    def test_close_on_or_before_query_shape(self):
        session, captured = _session_capturing()
        asyncio.run(close_on_or_before(session, 7, date(2026, 9, 14)))
        sql = _sql(captured[0])
        assert "market_data_daily" in sql
        assert "<=" in sql
        assert "order by" in sql

    def test_nth_trading_day_close_uses_offset(self):
        session, captured = _session_capturing()
        asyncio.run(nth_trading_day_close(session, 7, date(2026, 9, 14), 3))
        sql = _sql(captured[0])
        assert ">" in sql
        assert "offset 2" in sql

    def test_latest_closes_uses_distinct_on(self):
        result = MagicMock()
        result.all.return_value = []
        session, captured = _session_capturing(result)
        asyncio.run(latest_closes(session, [1, 2]))
        compiled = str(captured[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "distinct on" in compiled.lower()


class TestLearningLoaders:
    def test_load_signals_empty_views(self):
        session = AsyncMock()
        assert asyncio.run(load_signals_for_views(session, [])) == {}
        session.execute.assert_not_called()

    def test_load_signals_groups_and_drops_unwanted(self):
        wanted = SimpleNamespace(stock_id=1, trading_date=date(2026, 9, 14), composite_score=0.5)
        extra = SimpleNamespace(stock_id=1, trading_date=date(2026, 9, 15), composite_score=0.9)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [wanted, extra]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        view = SimpleNamespace(stock_id=1, trading_date=date(2026, 9, 14))
        grouped = asyncio.run(load_signals_for_views(session, [view]))
        assert grouped == {(1, date(2026, 9, 14)): [wanted]}

    def test_fetch_learning_view_outcomes_returns_rows(self):
        pair = (SimpleNamespace(id=1), SimpleNamespace(is_correct=True))
        result = MagicMock()
        result.all.return_value = [pair]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        cutoff = datetime(2026, 9, 1, tzinfo=UTC)
        rows = asyncio.run(fetch_learning_view_outcomes(session, cutoff, sector_id=3))
        assert rows == [pair]
        session.execute.assert_awaited_once()

    def test_fetch_learning_query_includes_conviction_floor(self):
        result = MagicMock()
        result.all.return_value = []
        session, captured = _session_capturing(result)
        cutoff = datetime(2026, 9, 1, tzinfo=UTC)
        asyncio.run(fetch_learning_view_outcomes(session, cutoff, sector_id=3))
        sql = _sql(captured[0])
        assert "window_days" in sql
        assert str(MIN_CONVICTION) in sql or "0.2" in sql
        assert "sector_id" in sql
        assert "order by" not in sql

    def test_fetch_learning_query_orders_when_requested(self):
        result = MagicMock()
        result.all.return_value = []
        session, captured = _session_capturing(result)
        cutoff = datetime(2026, 9, 1, tzinfo=UTC)
        asyncio.run(fetch_learning_view_outcomes(session, cutoff, order_by_date=True))
        sql = _sql(captured[0])
        assert "order by" in sql
        assert "trading_date" in sql
        assert "sector_id" not in sql
