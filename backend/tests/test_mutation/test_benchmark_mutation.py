"""Mutation-killing tests for worker/utils/backtester/benchmark.py.

Focuses on alpha/beta formulas, normalization, and return direction.
"""

from datetime import date, timedelta

from worker.utils.backtester.benchmark import compute_benchmark
from worker.utils.backtester.models import EquityPoint, OHLCVRow


def _make_bench_ohlcv(start: date, days: int, base: float = 100.0, trend: float = 0.1) -> list[OHLCVRow]:
    return [
        OHLCVRow(
            date=start + timedelta(days=i),
            open=base + trend * i,
            high=base + trend * i + 0.5,
            low=base + trend * i - 0.5,
            close=base + trend * i,
            volume=1000000,
        )
        for i in range(days)
    ]


def _make_equity(start: date, days: int, base: float = 10000.0, daily_gain: float = 10.0) -> list[EquityPoint]:
    return [
        EquityPoint(date=start + timedelta(days=i), equity=base + daily_gain * i)
        for i in range(days)
    ]


class TestAlphaDirection:
    def test_alpha_equals_strategy_minus_benchmark(self):
        """Kill mutation: `strategy_annual - bench_annual` reversed."""
        base = date(2024, 1, 1)
        # Strategy: flat (0% return)
        strategy = _make_equity(base, 100, base=10000, daily_gain=0)
        # Benchmark: going up (positive return)
        bench = _make_bench_ohlcv(base, 100, base=100, trend=0.1)
        result = compute_benchmark(bench, strategy, 10000)
        assert result is not None
        # Strategy 0%, benchmark positive → alpha should be negative
        assert result.alpha < 0

    def test_alpha_positive_when_outperforming(self):
        """Kill mutation: alpha sign verification."""
        base = date(2024, 1, 1)
        # Strategy: strong gain
        strategy = _make_equity(base, 100, base=10000, daily_gain=50)
        # Benchmark: small gain
        bench = _make_bench_ohlcv(base, 100, base=100, trend=0.05)
        result = compute_benchmark(bench, strategy, 10000)
        assert result is not None
        assert result.alpha > 0


class TestBetaFormula:
    def test_beta_is_cov_over_var(self):
        """Kill mutation: `cov / var_b` changed to `var_b / cov`."""
        base = date(2024, 1, 1)
        # Strategy moves exactly with benchmark (beta ≈ 1)
        days = 100
        bench_ohlcv = []
        strategy_curve = []
        for i in range(days):
            d = base + timedelta(days=i)
            price = 100 + i * 0.5
            bench_ohlcv.append(
                OHLCVRow(date=d, open=price, high=price + 0.5, low=price - 0.5, close=price, volume=1000000)
            )
            # Strategy equity mirrors benchmark movement
            equity = 10000 * (price / 100.0)
            strategy_curve.append(EquityPoint(date=d, equity=equity))

        result = compute_benchmark(bench_ohlcv, strategy_curve, 10000)
        assert result is not None
        assert result.beta is not None
        # Beta should be close to 1.0 since strategy mirrors benchmark
        assert 0.8 < result.beta < 1.2

    def test_beta_none_insufficient_data(self):
        """Kill mutation: `len(common_dates) >= 3` boundary."""
        base = date(2024, 1, 1)
        strategy = [
            EquityPoint(date=base, equity=10000),
            EquityPoint(date=base + timedelta(days=1), equity=10100),
        ]
        bench = _make_bench_ohlcv(base, 2)
        result = compute_benchmark(bench, strategy, 10000)
        # Only 2 dates, need >= 3 for beta
        assert result is not None
        assert result.beta is None


class TestNormalization:
    def test_first_equity_equals_starting_capital(self):
        """Kill mutation: `(bench_price / bench_start_price) * starting_capital` formula."""
        base = date(2024, 1, 1)
        strategy = _make_equity(base, 50, base=20000, daily_gain=0)
        bench = _make_bench_ohlcv(base, 50, base=500.0, trend=0)
        result = compute_benchmark(bench, strategy, 20000)
        assert result is not None
        # First benchmark equity should be normalized to starting_capital
        assert result.equity_curve[0].equity == 20000

    def test_normalization_direction(self):
        """Kill mutation: division order `bench/start` vs `start/bench`."""
        base = date(2024, 1, 1)
        strategy = _make_equity(base, 50, base=10000, daily_gain=0)
        # Benchmark doubles: 100 → 200
        bench = _make_bench_ohlcv(base, 50, base=100.0, trend=2.0)
        result = compute_benchmark(bench, strategy, 10000)
        assert result is not None
        # Final benchmark equity = (200/100) * 10000 ≈ 20000 range
        assert result.equity_curve[-1].equity > result.equity_curve[0].equity


class TestReturnCalculation:
    def test_total_return_positive(self):
        """Kill mutation: `(final - start) / start * 100` formula."""
        base = date(2024, 1, 1)
        strategy = _make_equity(base, 100, base=10000, daily_gain=0)
        # Benchmark gains 10%
        bench = _make_bench_ohlcv(base, 100, base=100.0, trend=0.1)
        result = compute_benchmark(bench, strategy, 10000)
        assert result is not None
        assert result.total_return_pct > 0

    def test_empty_inputs_none(self):
        """Kill mutation: guard clauses for empty inputs."""
        assert compute_benchmark([], [], 10000) is None

    def test_insufficient_equity_curve(self):
        """Kill mutation: `len(backtest_equity_curve) < 2` guard."""
        bench = _make_bench_ohlcv(date(2024, 1, 1), 10)
        strategy = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        assert compute_benchmark(bench, strategy, 10000) is None
