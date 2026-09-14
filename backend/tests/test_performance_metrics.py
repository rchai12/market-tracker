"""Shared Sharpe / drawdown / Jensen alpha-beta."""

import math

from worker.utils.performance_metrics import (
    TRADING_DAYS,
    daily_returns,
    jensen_alpha_beta,
    max_drawdown_pct,
    sharpe_ratio,
)


class TestDailyReturns:
    def test_skips_non_positive_base(self):
        assert daily_returns([0.0, 10.0, 12.0]) == [0.2]

    def test_empty(self):
        assert daily_returns([]) == []
        assert daily_returns([100.0]) == []


class TestSharpe:
    def test_uptrend_positive(self):
        values = [100.0 + i for i in range(20)]
        assert sharpe_ratio(daily_returns(values)) > 0

    def test_insufficient(self):
        assert sharpe_ratio([]) is None
        assert sharpe_ratio([0.01]) is None

    def test_zero_vol_none(self):
        assert sharpe_ratio([0.0, 0.0, 0.0]) is None

    def test_sqrt_252(self):
        rets = [0.01, 0.02, -0.005, 0.015]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        expected = (mean / math.sqrt(var)) * math.sqrt(TRADING_DAYS)
        assert abs(sharpe_ratio(rets) - expected) < 1e-12


class TestMaxDrawdown:
    def test_peak_to_trough(self):
        assert abs(max_drawdown_pct([100.0, 200.0, 150.0]) - 25.0) < 1e-12

    def test_empty_zero(self):
        assert max_drawdown_pct([]) == 0.0

    def test_monotonic_zero(self):
        assert max_drawdown_pct([1.0, 2.0, 3.0]) == 0.0


class TestJensenAlphaBeta:
    def test_levered_beta_two_zero_alpha(self):
        bench = [0.01, -0.004901960784313725]
        port = [r * 2 for r in bench]
        alpha, beta = jensen_alpha_beta(port, bench)
        assert abs(beta - 2.0) < 1e-9
        assert abs(alpha) < 1e-6

    def test_positive_alpha_not_from_beta(self):
        bench = [0.01, -0.01]
        port = [0.03, -0.01]
        alpha, beta = jensen_alpha_beta(port, bench)
        assert beta is not None
        assert alpha > 0

    def test_flat_strategy_zero_beta_zero_alpha(self):
        port = [0.0, 0.0, 0.0]
        bench = [0.01, -0.01, 0.02]
        alpha, beta = jensen_alpha_beta(port, bench)
        assert abs(beta) < 1e-12
        assert abs(alpha) < 1e-12

    def test_insufficient(self):
        assert jensen_alpha_beta([0.01], [0.01]) == (None, None)

    def test_zero_bench_variance(self):
        assert jensen_alpha_beta([0.01, 0.02], [0.0, 0.0]) == (None, None)
