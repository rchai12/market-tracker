"""Phase 24b: excess return vs sector ETF for daily-view is_correct."""

import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from worker.tasks.signals.outcome_evaluator import (
    _evaluate_single_daily_view,
    _sector_benchmark_return,
)
from worker.utils.daily_aggregation import SECTOR_BENCHMARK, excess_return_pct, outcome_is_correct


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


class TestSectorBenchmarkMap:
    def test_known_sectors_map_to_etfs(self):
        assert SECTOR_BENCHMARK["Energy"] == "XLE"
        assert SECTOR_BENCHMARK["Financials"] == "XLF"
        assert SECTOR_BENCHMARK["Technology"] == "XLK"
        assert SECTOR_BENCHMARK["Communication Services"] == "XLC"
        assert SECTOR_BENCHMARK["Consumer Discretionary"] == "XLY"

    def test_market_etfs_have_no_benchmark(self):
        assert SECTOR_BENCHMARK["Market ETFs"] is None


class TestExcessReturnMath:
    def test_stock_minus_sector(self):
        assert abs(excess_return_pct(-0.003, -0.02) - 0.017) < 1e-9

    def test_none_benchmark_returns_none(self):
        assert excess_return_pct(0.02, None) is None

    def test_bullish_correct_on_positive_excess(self):
        assert outcome_is_correct("bullish", 0.017) is True
        assert outcome_is_correct("bullish", -0.003) is False

    def test_bearish_correct_on_negative_excess(self):
        assert outcome_is_correct("bearish", -0.01) is True
        assert outcome_is_correct("bearish", 0.01) is False


class TestEvaluateExcessReturn:
    def test_bullish_correct_when_stock_beats_sector_despite_absolute_loss(self):
        view = _view(direction="bullish")
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=100.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=99.7),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_name_for_stock",
                new=AsyncMock(return_value="Technology"),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_benchmark_return",
                new=AsyncMock(return_value=-0.02),
            ),
        ):
            outcome = asyncio.run(_evaluate_single_daily_view(AsyncMock(), view, 1))
        assert outcome is not None
        assert outcome.is_correct is True
        assert abs(outcome.price_change_pct - (-0.003)) < 1e-9
        assert abs(outcome.sector_return_pct - (-0.02)) < 1e-9
        assert abs(outcome.excess_return_pct - 0.017) < 1e-9

    def test_bullish_wrong_when_stock_lags_sector_despite_absolute_gain(self):
        view = _view(direction="bullish")
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=100.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=101.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_name_for_stock",
                new=AsyncMock(return_value="Energy"),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_benchmark_return",
                new=AsyncMock(return_value=0.03),
            ),
        ):
            outcome = asyncio.run(_evaluate_single_daily_view(AsyncMock(), view, 1))
        assert outcome is not None
        assert outcome.is_correct is False
        assert abs(outcome.price_change_pct - 0.01) < 1e-9
        assert abs(outcome.excess_return_pct - (-0.02)) < 1e-9

    def test_market_etfs_use_absolute_return(self):
        bench = AsyncMock(return_value=0.05)
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
                new=AsyncMock(return_value="Market ETFs"),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_benchmark_return",
                new=bench,
            ),
        ):
            outcome = asyncio.run(_evaluate_single_daily_view(AsyncMock(), _view(), 1))
        assert outcome is not None
        assert outcome.is_correct is True
        assert abs(outcome.price_change_pct - 0.02) < 1e-9
        assert outcome.sector_return_pct is None
        assert outcome.excess_return_pct is None
        bench.assert_not_awaited()

    def test_missing_etf_data_falls_back_to_absolute(self):
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
                new=AsyncMock(return_value="Financials"),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._sector_benchmark_return",
                new=AsyncMock(return_value=None),
            ),
        ):
            outcome = asyncio.run(_evaluate_single_daily_view(AsyncMock(), _view(), 1))
        assert outcome is not None
        assert outcome.is_correct is True
        assert outcome.sector_return_pct is None
        assert outcome.excess_return_pct is None


class TestSectorBenchmarkReturnHelper:
    def test_computes_etf_return(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = 99
        session.execute = AsyncMock(return_value=result)
        with (
            patch(
                "worker.tasks.signals.outcome_evaluator._get_close_on_or_before",
                new=AsyncMock(return_value=50.0),
            ),
            patch(
                "worker.tasks.signals.outcome_evaluator._get_nth_trading_day_close",
                new=AsyncMock(return_value=51.0),
            ),
        ):
            ret = asyncio.run(_sector_benchmark_return(session, "Technology", date(2026, 9, 13), 1))
        assert abs(ret - 0.02) < 1e-9

    def test_market_etfs_return_none(self):
        assert asyncio.run(_sector_benchmark_return(AsyncMock(), "Market ETFs", date(2026, 9, 13), 1)) is None

    def test_missing_etf_stock_returns_none(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        assert asyncio.run(_sector_benchmark_return(session, "Energy", date(2026, 9, 13), 1)) is None
