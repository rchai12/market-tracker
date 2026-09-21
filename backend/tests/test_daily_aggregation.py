"""Phase 24: daily net-view aggregation and trading-date assignment."""

import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from worker.tasks.signals.signal_generator import _resolve_trading_date, _upsert_daily_view
from worker.utils.daily_aggregation import (
    MIN_CONVICTION,
    compute_net_view,
    expand_view_credits,
    in_cash_session,
    pick_trading_date,
    trading_date_lower_bound,
)

ET = ZoneInfo("America/New_York")


def _sig(composite: float, direction: str, **kwargs):
    return SimpleNamespace(composite_score=composite, direction=direction, **kwargs)


class TestNetScore:
    def test_strong_outweighs_weak(self):
        view = compute_net_view(
            [
                _sig(0.8, "bullish"),
                _sig(0.2, "bearish"),
            ]
        )
        assert view is not None
        assert view.direction == "bullish"
        assert abs(view.net_score - 0.6) < 1e-9
        assert abs(view.conviction - 0.6) < 1e-9
        assert view.signal_count == 2

    def test_equal_opposite_is_zero_conviction(self):
        view = compute_net_view([_sig(0.5, "bullish"), _sig(0.5, "bearish")])
        assert view is not None
        assert abs(view.net_score) < 1e-12
        assert view.conviction < MIN_CONVICTION

    def test_signed_composite_not_double_flipped(self):
        # Live composites are already signed; vote uses abs(composite) * direction sign.
        view = compute_net_view([_sig(-0.6, "bearish"), _sig(0.2, "bullish")])
        assert view is not None
        assert view.direction == "bearish"
        assert view.net_score < 0

    def test_empty_returns_none(self):
        assert compute_net_view([]) is None
        assert compute_net_view([_sig(0.0, "bullish")]) is None

    def test_low_conviction_below_learning_floor(self):
        view = compute_net_view(
            [
                _sig(0.30, "bullish"),
                _sig(0.25, "bearish"),
            ]
        )
        assert view is not None
        assert view.conviction < MIN_CONVICTION


class TestTradingDate:
    def test_during_session_same_day(self):
        ts = datetime(2026, 9, 14, 10, 0, tzinfo=ET)
        assert trading_date_lower_bound(ts) == date(2026, 9, 14)
        assert in_cash_session(ts) is True

    def test_premarket_weekday_same_day(self):
        ts = datetime(2026, 9, 14, 8, 0, tzinfo=ET)
        assert trading_date_lower_bound(ts) == date(2026, 9, 14)
        assert in_cash_session(ts) is False

    def test_after_close_next_day(self):
        ts = datetime(2026, 9, 14, 16, 0, tzinfo=ET)
        assert trading_date_lower_bound(ts) == date(2026, 9, 15)

    def test_weekend_advances_calendar(self):
        ts = datetime(2026, 9, 12, 12, 0, tzinfo=ET)  # Saturday
        assert trading_date_lower_bound(ts) == date(2026, 9, 13)

    def test_pick_skips_holiday(self):
        floor = date(2026, 9, 7)  # Monday Labor Day 2026
        available = [date(2026, 9, 4), date(2026, 9, 8), date(2026, 9, 9)]
        assert pick_trading_date(floor, available) == date(2026, 9, 8)

    def test_pick_empty_calendar(self):
        assert pick_trading_date(date(2026, 9, 14), []) is None


class TestResolveAndUpsert:
    def test_resolve_trading_date_uses_market_calendar(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = date(2026, 9, 15)
        session.execute = AsyncMock(return_value=result)
        generated = datetime(2026, 9, 14, 20, 30, tzinfo=ET)
        found = asyncio.run(_resolve_trading_date(session, 1, generated))
        assert found == date(2026, 9, 15)

    def test_upsert_skips_empty_group(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)
        asyncio.run(_upsert_daily_view(session, 1, date(2026, 9, 14)))
        assert session.execute.await_count == 1

    def test_upsert_skips_none_date(self):
        session = AsyncMock()
        asyncio.run(_upsert_daily_view(session, 1, None))
        session.execute.assert_not_called()

    def test_upsert_writes_when_signals_exist(self):
        session = AsyncMock()
        select_result = MagicMock()
        select_result.scalars.return_value.all.return_value = [_sig(0.5, "bullish")]
        session.execute = AsyncMock(return_value=select_result)
        asyncio.run(_upsert_daily_view(session, 1, date(2026, 9, 14)))
        assert session.execute.await_count == 2


class TestExpandCredits:
    def test_proportional_share(self):
        rows = expand_view_credits(
            [_sig(0.7, "bullish", sentiment_score=0.5), _sig(0.3, "bullish", sentiment_score=0.1)],
            price_change_pct=0.05,
            is_correct=True,
        )
        assert len(rows) == 2
        shares = sorted(r.share for r in rows)
        assert abs(shares[0] - 0.3) < 1e-9
        assert abs(shares[1] - 0.7) < 1e-9
        magnitudes = sorted(abs(r.price_change_pct) for r in rows)
        assert abs(magnitudes[0] - 0.015) < 1e-9
        assert abs(magnitudes[1] - 0.035) < 1e-9
