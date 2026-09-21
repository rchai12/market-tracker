"""Phase 24: daily-view outcome evaluation."""

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from worker.tasks.signals.outcome_evaluator import _evaluate_single_daily_view
from worker.utils.daily_aggregation import MIN_CONVICTION, compute_net_view


def _view(**overrides):
    base = dict(
        id=1,
        stock_id=10,
        trading_date=date(2026, 9, 14),
        direction="bullish",
        conviction=0.54,
        baseline_close=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestEvaluateDailyView:
    def test_bullish_correct_when_price_up(self):
        view = _view()
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=100.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=102.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_name_for_stock",
                new=AsyncMock(return_value=None),
            ),
        ):
            outcome = asyncio.run(_evaluate_single_daily_view(AsyncMock(), view, 1))
        assert outcome is not None
        assert outcome.is_correct is True
        assert abs(outcome.price_change_pct - 0.02) < 1e-9
        assert outcome.excess_return_pct is None
        assert view.baseline_close == 100.0

    def test_bearish_correct_when_price_down(self):
        view = _view(direction="bearish")
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=100.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=97.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_name_for_stock",
                new=AsyncMock(return_value=None),
            ),
        ):
            outcome = asyncio.run(_evaluate_single_daily_view(AsyncMock(), view, 1))
        assert outcome is not None
        assert outcome.is_correct is True
        assert outcome.price_change_pct < 0

    def test_missing_baseline_skips(self):
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=102.0),
            ),
        ):
            assert asyncio.run(_evaluate_single_daily_view(AsyncMock(), _view(), 1)) is None

    def test_missing_outcome_close_skips(self):
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=100.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=None),
            ),
        ):
            assert asyncio.run(_evaluate_single_daily_view(AsyncMock(), _view(), 3)) is None

    def test_one_day_uses_predicted_session_close(self):
        """1-day window is the close on trading_date vs the prior session."""
        view = _view(trading_date=date(2026, 9, 14))
        captured = {}

        async def fake_nth(_session, stock_id, start_date, n):
            captured["start"] = start_date
            captured["n"] = n
            captured["stock_id"] = stock_id
            return 101.0

        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=100.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=fake_nth,
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_name_for_stock",
                new=AsyncMock(return_value=None),
            ),
        ):
            asyncio.run(_evaluate_single_daily_view(AsyncMock(), view, 1))
        assert captured["start"] == date(2026, 9, 13)
        assert captured["n"] == 1
        assert captured["stock_id"] == 10

    def test_conviction_floor_excludes_ambiguous_views(self):
        view = compute_net_view(
            [
                SimpleNamespace(composite_score=0.22, direction="bullish"),
                SimpleNamespace(composite_score=0.20, direction="bearish"),
            ]
        )
        assert view is not None
        assert view.conviction < MIN_CONVICTION
