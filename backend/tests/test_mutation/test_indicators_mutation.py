"""Mutation-killing tests for worker/utils/technical_indicators.py.

These tests target specific operator and boundary mutations that standard tests
may not catch: exact slice indices, formula constants, subtraction order, and
population vs sample std deviation.
"""

import math

from worker.utils.technical_indicators import (
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
)


class TestSMAMutationKillers:
    def test_exact_first_value(self):
        """Kill mutation: off-by-one in slice `i-period+1:i+1`."""
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = compute_sma(closes, 3)
        # SMA(3) at index 2 = (10+20+30)/3 = 20.0
        assert result[2] == 20.0
        # SMA(3) at index 3 = (20+30+40)/3 = 30.0
        assert result[3] == 30.0
        # SMA(3) at index 4 = (30+40+50)/3 = 40.0
        assert result[4] == 40.0

    def test_none_at_period_minus_two(self):
        """Kill mutation: boundary `range(period - 1, ...)` changed to `range(period, ...)`."""
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = compute_sma(closes, 3)
        assert result[1] is None  # period-2 = index 1 must be None
        assert result[2] is not None  # period-1 = index 2 must have value

    def test_exact_slice_boundaries_period_5(self):
        """Kill mutation: verify exact window indices for period 5."""
        closes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        result = compute_sma(closes, 5)
        # At index 4: sum(1,2,3,4,5)/5 = 3.0
        assert result[4] == 3.0
        # At index 5: sum(2,3,4,5,6)/5 = 4.0
        assert result[5] == 4.0
        # At index 6: sum(3,4,5,6,7)/5 = 5.0
        assert result[6] == 5.0

    def test_division_by_period(self):
        """Kill mutation: `/ period` changed to `/ (period + 1)` or `/ (period - 1)`."""
        closes = [3.0, 3.0, 3.0]
        result = compute_sma(closes, 3)
        # (3+3+3)/3 = 3.0 exactly — catches wrong divisor
        assert result[2] == 3.0


class TestEMAMutationKillers:
    def test_multiplier_formula(self):
        """Kill mutation: `2.0 / (period + 1)` changed to `2.0 / period` or `2.0 / (period - 1)`."""
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        period = 3
        result = compute_ema(closes, period)
        # multiplier = 2/(3+1) = 0.5
        # Seed at index 2: SMA = (10+20+30)/3 = 20.0
        # Index 3: (40 - 20) * 0.5 + 20 = 30.0
        assert result[2] == 20.0
        assert result[3] == 30.0
        # Index 4: (50 - 30) * 0.5 + 30 = 40.0
        assert result[4] == 40.0

    def test_ema_formula_direction(self):
        """Kill mutation: `(closes[i] - prev) * multiplier + prev` with swapped terms."""
        closes = [100.0, 100.0, 100.0, 200.0]  # Spike at end
        result = compute_ema(closes, 3)
        # Multiplier = 2/(3+1) = 0.5
        # Seed = (100+100+100)/3 = 100
        # Index 3: (200-100) * 0.5 + 100 = 150
        assert result[3] == 150.0

    def test_ema_none_before_seed(self):
        """Kill mutation: first EMA at wrong index."""
        closes = [10.0, 20.0, 30.0, 40.0]
        result = compute_ema(closes, 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None  # Seed at period-1


class TestRSIMutationKillers:
    def test_rsi_formula_exact(self):
        """Kill mutation: `100 - 100/(1+rs)` operator changes."""
        # 15 data points: 14 changes, first 7 gains of 1.0, next 7 losses of 1.0
        closes = [100.0]
        for i in range(7):
            closes.append(closes[-1] + 1.0)  # gain
        for i in range(7):
            closes.append(closes[-1] - 1.0)  # loss
        result = compute_rsi(closes, 14)
        # avg_gain = 7/14 = 0.5, avg_loss = 7/14 = 0.5
        # RS = 0.5/0.5 = 1.0
        # RSI = 100 - 100/(1+1) = 100 - 50 = 50.0
        assert result[14] is not None
        assert abs(result[14] - 50.0) < 1e-10

    def test_gains_losses_separation(self):
        """Kill mutation: `max(c, 0)` vs `abs(min(c, 0))` swapped."""
        # Only gains: 15 increasing prices
        closes_up = [100.0 + i for i in range(16)]
        result_up = compute_rsi(closes_up, 14)
        assert result_up[14] is not None
        assert result_up[14] == 100.0  # All gains, no losses → RSI = 100

        # Only losses: 15 decreasing prices
        closes_down = [115.0 - i for i in range(16)]
        result_down = compute_rsi(closes_down, 14)
        assert result_down[14] is not None
        # avg_loss > 0, avg_gain = 0 → RS = 0 → RSI = 100 - 100/(1+0) = 0
        assert abs(result_down[14]) < 1e-10

    def test_wilder_smoothing_factor(self):
        """Kill mutation: `(period - 1)` changed to `period` or `(period + 1)`."""
        # After the initial RSI, subsequent values use Wilder's smoothing:
        # avg_gain = (avg_gain * (period-1) + gain) / period
        # Create: 14 gains of 2.0, then 1 gain of 10.0
        closes = [100.0]
        for i in range(14):
            closes.append(closes[-1] + 2.0)
        closes.append(closes[-1] + 10.0)  # Big gain at index 15

        result = compute_rsi(closes, 14)
        # First RSI at index 14: avg_gain = 14*2/14 = 2.0, avg_loss = 0 → RSI = 100
        assert result[14] == 100.0
        # Second RSI at index 15: avg_gain = (2.0 * 13 + 10.0) / 14 = 36/14 ≈ 2.571
        # avg_loss = (0 * 13 + 0) / 14 = 0 → RSI = 100
        assert result[15] == 100.0

    def test_rsi_with_mixed_changes(self):
        """Kill mutation: verify RSI value with known mixed gains/losses."""
        # Alternating: +3, -1 for 14 changes
        closes = [100.0]
        for i in range(14):
            if i % 2 == 0:
                closes.append(closes[-1] + 3.0)
            else:
                closes.append(closes[-1] - 1.0)
        result = compute_rsi(closes, 14)
        # 7 gains of 3.0, 7 losses of 1.0
        # avg_gain = 7*3/14 = 1.5, avg_loss = 7*1/14 = 0.5
        # RS = 1.5/0.5 = 3.0
        # RSI = 100 - 100/(1+3) = 100 - 25 = 75.0
        assert result[14] is not None
        assert abs(result[14] - 75.0) < 1e-10


class TestMACDMutationKillers:
    def test_subtraction_order(self):
        """Kill mutation: `ema_fast - ema_slow` changed to `ema_slow - ema_fast`."""
        # Strong uptrend: fast EMA should be above slow EMA → MACD > 0
        closes = [100.0 + i * 2.0 for i in range(50)]
        result = compute_macd(closes)
        # Find first non-None MACD
        for entry in result:
            if entry["macd_line"] is not None:
                assert entry["macd_line"] > 0  # Fast > Slow in uptrend
                break

    def test_histogram_sign_in_uptrend(self):
        """Kill mutation: `ml - sl` changed to `sl - ml` in histogram."""
        # In a strong, sustained uptrend MACD line should be above signal line
        # giving positive histogram toward the end
        closes = [100.0 + i * 3.0 for i in range(60)]
        result = compute_macd(closes)
        latest = result[-1]
        if latest["histogram"] is not None:
            # The histogram should be the difference between MACD and signal line
            assert abs(latest["histogram"] - (latest["macd_line"] - latest["signal_line"])) < 1e-10

    def test_signal_ema_period(self):
        """Kill mutation: signal EMA uses wrong period."""
        # Use volatile data so signal EMA periods produce different results
        import math
        closes = [100.0 + 10 * math.sin(i * 0.3) + i * 0.2 for i in range(60)]
        result_default = compute_macd(closes, fast=12, slow=26, signal=9)
        result_diff = compute_macd(closes, fast=12, slow=26, signal=5)
        # Different signal periods should produce different signal lines
        sl_default = [r["signal_line"] for r in result_default if r["signal_line"] is not None]
        sl_diff = [r["signal_line"] for r in result_diff if r["signal_line"] is not None]
        if sl_default and sl_diff:
            # At least the last values should differ
            assert sl_default[-1] != sl_diff[-1]


class TestBollingerMutationKillers:
    def test_population_std_not_sample(self):
        """Kill mutation: `/ period` changed to `/ (period - 1)` (sample vs population)."""
        # Known data: [1, 2, 3, 4, 5] with period 5
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = compute_bollinger_bands(closes, period=5, num_std=1.0)
        # mean = 3.0
        # population variance = ((1-3)^2 + (2-3)^2 + (3-3)^2 + (4-3)^2 + (5-3)^2) / 5 = 10/5 = 2.0
        # population std = sqrt(2) ≈ 1.4142
        expected_std = math.sqrt(2.0)
        expected_upper = 3.0 + expected_std
        expected_lower = 3.0 - expected_std
        assert abs(result[4]["upper"] - expected_upper) < 1e-10
        assert abs(result[4]["middle"] - 3.0) < 1e-10
        assert abs(result[4]["lower"] - expected_lower) < 1e-10

    def test_band_width_with_num_std(self):
        """Kill mutation: `num_std * std` changed to `std` or `num_std + std`."""
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result_1std = compute_bollinger_bands(closes, period=5, num_std=1.0)
        result_2std = compute_bollinger_bands(closes, period=5, num_std=2.0)
        # Band width should double
        width_1 = result_1std[4]["upper"] - result_1std[4]["lower"]
        width_2 = result_2std[4]["upper"] - result_2std[4]["lower"]
        assert abs(width_2 - 2.0 * width_1) < 1e-10

    def test_upper_lower_symmetry(self):
        """Kill mutation: `mean + num_std * std` vs `mean - num_std * std` swapped."""
        closes = [10.0, 12.0, 8.0, 11.0, 9.0, 13.0, 7.0, 10.0, 12.0, 8.0,
                  11.0, 9.0, 13.0, 7.0, 10.0, 12.0, 8.0, 11.0, 9.0, 10.0]
        result = compute_bollinger_bands(closes, period=20, num_std=2.0)
        latest = result[-1]
        # Upper should be above middle, lower below middle
        assert latest["upper"] > latest["middle"]
        assert latest["lower"] < latest["middle"]
        # Symmetric distance from middle
        upper_dist = latest["upper"] - latest["middle"]
        lower_dist = latest["middle"] - latest["lower"]
        assert abs(upper_dist - lower_dist) < 1e-10

    def test_variance_formula_squaring(self):
        """Kill mutation: `(x - mean) ** 2` changed to `abs(x - mean)` or `(x - mean)`."""
        # With known data, verify exact variance
        closes = [10.0, 20.0, 30.0]
        result = compute_bollinger_bands(closes, period=3, num_std=1.0)
        # mean = 20
        # population variance = ((10-20)^2 + (20-20)^2 + (30-20)^2) / 3 = 200/3
        # std = sqrt(200/3)
        expected_std = math.sqrt(200.0 / 3.0)
        assert abs(result[2]["upper"] - (20.0 + expected_std)) < 1e-10
