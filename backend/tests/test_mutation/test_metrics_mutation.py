"""Mutation-killing tests for worker/utils/backtester/metrics.py.

These tests verify exact formula outputs with known inputs to catch operator
mutations (subtraction order, division direction, wrong constants).
"""

import math
from datetime import date, timedelta

from worker.utils.backtester.metrics import (
    _compute_max_drawdown,
    _compute_sharpe,
    _empty_metrics,
    compute_metrics,
)
from worker.utils.backtester.models import EquityPoint, TradeRecord


class TestTotalReturnExact:
    def test_positive_return_exact_value(self):
        """Kill mutation: `(final - start) / start * 100` operator changes."""
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=10000),
            EquityPoint(date=date(2024, 1, 2), equity=12000),
        ]
        result = compute_metrics(equity, [], 10000)
        # (12000 - 10000) / 10000 * 100 = 20.0
        assert result["total_return_pct"] == 20.0

    def test_negative_return_exact_value(self):
        """Kill mutation: subtraction order `final - start` vs `start - final`."""
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=10000),
            EquityPoint(date=date(2024, 1, 2), equity=8000),
        ]
        result = compute_metrics(equity, [], 10000)
        # (8000 - 10000) / 10000 * 100 = -20.0
        assert result["total_return_pct"] == -20.0

    def test_small_gain(self):
        """Kill mutation: `* 100` removed or changed."""
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=10000),
            EquityPoint(date=date(2024, 1, 2), equity=10100),
        ]
        result = compute_metrics(equity, [], 10000)
        # (10100 - 10000) / 10000 * 100 = 1.0
        assert result["total_return_pct"] == 1.0


class TestAnnualizedReturn:
    def test_252_day_period_equals_total(self):
        """Kill mutation: `252 / trading_days` with wrong constant."""
        base = date(2024, 1, 1)
        equity = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * (2000 / 252))
            for i in range(252)
        ]
        result = compute_metrics(equity, [], 10000)
        # Over exactly 252 trading days, annualized ≈ total
        assert abs(result["annualized_return_pct"] - result["total_return_pct"]) < 0.5

    def test_annualized_formula_exact(self):
        """Kill mutation: `ratio ** (252/days) - 1` operator changes."""
        base = date(2024, 1, 1)
        # 100 days, final equity 11000 → 10% total return
        equity = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * 10)
            for i in range(100)
        ]
        result = compute_metrics(equity, [], 10000)
        # ratio = 10990/10000 = 1.099
        # annualized = (1.099^(252/100) - 1) * 100
        expected_ratio = equity[-1].equity / 10000
        expected_ann = (expected_ratio ** (252.0 / 100.0) - 1) * 100
        assert abs(result["annualized_return_pct"] - round(expected_ann, 4)) < 0.01

    def test_single_equity_point_zero(self):
        """Kill mutation: annualized return for single point should be 0."""
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, [], 10000)
        assert result["annualized_return_pct"] == 0.0


class TestSharpeRatio:
    def test_uptrend_positive_sharpe(self):
        """Kill mutation: mean/std ratio sign."""
        base = date(2024, 1, 1)
        # Monotonically increasing equity → positive daily returns
        equity = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * 50)
            for i in range(100)
        ]
        result = _compute_sharpe(equity)
        assert result is not None
        assert result > 0

    def test_downtrend_negative_sharpe(self):
        """Kill mutation: verify negative Sharpe in downtrend."""
        base = date(2024, 1, 1)
        equity = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 - i * 20)
            for i in range(100)
        ]
        result = _compute_sharpe(equity)
        assert result is not None
        assert result < 0

    def test_sqrt_252_annualization(self):
        """Kill mutation: `sqrt(252)` changed to `252` or `sqrt(365)`."""
        base = date(2024, 1, 1)
        equity = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * 10)
            for i in range(50)
        ]
        result = _compute_sharpe(equity)
        assert result is not None

        # Manually compute to verify sqrt(252) factor
        equities = [p.equity for p in equity]
        daily_returns = [
            (equities[i] - equities[i - 1]) / equities[i - 1]
            for i in range(1, len(equities))
        ]
        mean_r = sum(daily_returns) / len(daily_returns)
        var_r = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
        std_r = math.sqrt(var_r)
        expected = (mean_r / std_r) * math.sqrt(252)
        assert abs(result - expected) < 1e-10

    def test_insufficient_data_returns_none(self):
        """Kill mutation: `len < 2` boundary."""
        assert _compute_sharpe([]) is None
        assert _compute_sharpe([EquityPoint(date=date(2024, 1, 1), equity=10000)]) is None


class TestMaxDrawdown:
    def test_exact_drawdown_percentage(self):
        """Kill mutation: `(peak - equity) / peak * 100` operator changes."""
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=10000),
            EquityPoint(date=date(2024, 1, 2), equity=20000),  # Peak
            EquityPoint(date=date(2024, 1, 3), equity=15000),  # 25% drawdown from 20000
        ]
        result = _compute_max_drawdown(equity)
        assert abs(result - 25.0) < 1e-10

    def test_monotonic_increase_zero_drawdown(self):
        """Kill mutation: ensure 0% drawdown for monotonic increase."""
        equity = [
            EquityPoint(date=date(2024, 1, i + 1), equity=10000 + i * 100)
            for i in range(20)
        ]
        assert _compute_max_drawdown(equity) == 0.0

    def test_peak_tracking(self):
        """Kill mutation: `if equity > peak` direction or missing update."""
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=100),
            EquityPoint(date=date(2024, 1, 2), equity=200),  # New peak
            EquityPoint(date=date(2024, 1, 3), equity=180),  # 10% dd from 200
            EquityPoint(date=date(2024, 1, 4), equity=300),  # New peak
            EquityPoint(date=date(2024, 1, 5), equity=210),  # 30% dd from 300
        ]
        result = _compute_max_drawdown(equity)
        assert abs(result - 30.0) < 1e-10

    def test_empty_curve(self):
        assert _compute_max_drawdown([]) == 0.0


class TestWinRateExact:
    def test_exact_win_rate(self):
        """Kill mutation: `wins / total * 100` operator changes."""
        trades = [
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 1, 1),
                price=110, shares=10, position_value=1100, portfolio_equity=11000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=10.0,
            ),
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 2, 1),
                price=90, shares=10, position_value=900, portfolio_equity=9000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=-5.0,
            ),
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 3, 1),
                price=120, shares=10, position_value=1200, portfolio_equity=12000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=15.0,
            ),
        ]
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, trades, 10000)
        # 2 wins out of 3 = 66.6667%
        assert abs(result["win_rate_pct"] - round(2 / 3 * 100, 4)) < 0.01

    def test_avg_loss_is_negative(self):
        """Kill mutation: avg_loss sign verification."""
        trades = [
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 1, 1),
                price=90, shares=10, position_value=900, portfolio_equity=9000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=-8.0,
            ),
        ]
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, trades, 10000)
        assert result["avg_loss_pct"] < 0

    def test_best_worst_trade(self):
        """Kill mutation: max/min for best/worst trade."""
        trades = [
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 1, 1),
                price=110, shares=10, position_value=1100, portfolio_equity=11000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=5.0,
            ),
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 2, 1),
                price=90, shares=10, position_value=900, portfolio_equity=9000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=-3.0,
            ),
        ]
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, trades, 10000)
        assert result["best_trade_pct"] == 5.0
        assert result["worst_trade_pct"] == -3.0

    def test_buy_trades_excluded_from_count(self):
        """Kill mutation: only sell trades should be counted."""
        trades = [
            TradeRecord(
                ticker="A", action="buy", trade_date=date(2024, 1, 1),
                price=100, shares=10, position_value=1000, portfolio_equity=10000,
                signal_score=0.5, signal_direction="bullish", signal_strength="moderate",
            ),
            TradeRecord(
                ticker="A", action="sell", trade_date=date(2024, 2, 1),
                price=110, shares=10, position_value=1100, portfolio_equity=11000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=10.0,
            ),
        ]
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, trades, 10000)
        assert result["total_trades"] == 1


class TestEmptyMetrics:
    def test_empty_metrics_structure(self):
        """Kill mutation: verify empty metrics return correct starting capital."""
        result = _empty_metrics(25000)
        assert result["total_return_pct"] == 0.0
        assert result["final_equity"] == 25000
        assert result["sharpe_ratio"] is None
        assert result["win_rate_pct"] is None
        assert result["total_trades"] == 0
