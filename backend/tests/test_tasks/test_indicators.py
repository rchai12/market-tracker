"""Tests for technical indicator calculations."""

from worker.utils.technical_indicators import (
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
)


class TestComputeSMA:
    def test_basic_sma(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = compute_sma(closes, 3)
        assert result[0] is None
        assert result[1] is None
        assert abs(result[2] - 2.0) < 1e-10
        assert abs(result[3] - 3.0) < 1e-10
        assert abs(result[4] - 4.0) < 1e-10

    def test_period_1_equals_input(self):
        closes = [10.0, 20.0, 30.0]
        result = compute_sma(closes, 1)
        for i, v in enumerate(closes):
            assert abs(result[i] - v) < 1e-10

    def test_insufficient_data(self):
        closes = [1.0, 2.0]
        result = compute_sma(closes, 5)
        assert all(v is None for v in result)

    def test_length_matches_input(self):
        closes = [1.0] * 20
        result = compute_sma(closes, 5)
        assert len(result) == len(closes)


class TestComputeEMA:
    def test_seed_equals_sma(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = compute_ema(closes, 3)
        # First EMA value at index 2 should equal SMA of first 3
        assert abs(result[2] - 2.0) < 1e-10

    def test_insufficient_data(self):
        closes = [1.0, 2.0]
        result = compute_ema(closes, 5)
        assert all(v is None for v in result)

    def test_length_matches_input(self):
        closes = [1.0] * 20
        result = compute_ema(closes, 5)
        assert len(result) == len(closes)

    def test_constant_prices_equal_price(self):
        closes = [50.0] * 20
        result = compute_ema(closes, 10)
        for v in result[9:]:
            assert abs(v - 50.0) < 1e-10


class TestComputeRSI:
    def test_all_gains_approaches_100(self):
        closes = [float(i) for i in range(1, 22)]  # 1 to 21, monotonically increasing
        result = compute_rsi(closes, 14)
        latest = result[-1]
        assert latest is not None
        assert latest > 95.0

    def test_all_losses_approaches_0(self):
        closes = [float(21 - i) for i in range(21)]  # 21 to 1, monotonically decreasing
        result = compute_rsi(closes, 14)
        latest = result[-1]
        assert latest is not None
        assert latest < 5.0

    def test_flat_prices_rsi_near_50(self):
        # Alternate small gains and losses
        closes = [100.0 + (0.5 if i % 2 == 0 else -0.5) for i in range(30)]
        result = compute_rsi(closes, 14)
        latest = result[-1]
        assert latest is not None
        assert 40.0 < latest < 60.0

    def test_insufficient_data_all_none(self):
        closes = [100.0] * 10
        result = compute_rsi(closes, 14)
        assert all(v is None for v in result)

    def test_first_values_are_none(self):
        closes = [float(i) for i in range(30)]
        result = compute_rsi(closes, 14)
        # First period entries should be None
        for i in range(14):
            assert result[i] is None
        assert result[14] is not None

    def test_rsi_bounded_0_to_100(self):
        closes = [100.0 + (i % 7) * 2 - 6 for i in range(50)]
        result = compute_rsi(closes, 14)
        for v in result:
            if v is not None:
                assert 0.0 <= v <= 100.0

    def test_length_matches_input(self):
        closes = [100.0] * 30
        result = compute_rsi(closes, 14)
        assert len(result) == len(closes)


class TestComputeMACD:
    def test_sufficient_data_produces_values(self):
        closes = [100.0 + i * 0.5 for i in range(50)]
        result = compute_macd(closes)
        # Should have MACD values toward the end
        latest = result[-1]
        assert latest["macd_line"] is not None

    def test_histogram_equals_macd_minus_signal(self):
        closes = [100.0 + i * 0.3 for i in range(60)]
        result = compute_macd(closes)
        for entry in result:
            if entry["macd_line"] is not None and entry["signal_line"] is not None:
                expected = entry["macd_line"] - entry["signal_line"]
                assert abs(entry["histogram"] - expected) < 1e-10

    def test_insufficient_data_all_none(self):
        closes = [100.0] * 10
        result = compute_macd(closes)
        assert all(r["macd_line"] is None for r in result)

    def test_length_matches_input(self):
        closes = [100.0] * 50
        result = compute_macd(closes)
        assert len(result) == len(closes)

    def test_uptrend_positive_macd(self):
        # Strong uptrend: fast EMA > slow EMA => MACD positive
        closes = [100.0 + i * 2.0 for i in range(50)]
        result = compute_macd(closes)
        latest = result[-1]
        if latest["macd_line"] is not None:
            assert latest["macd_line"] > 0


class TestComputeBollingerBands:
    def test_constant_prices_zero_bandwidth(self):
        closes = [100.0] * 25
        result = compute_bollinger_bands(closes, 20)
        latest = result[-1]
        assert latest["upper"] is not None
        assert abs(latest["upper"] - 100.0) < 1e-10
        assert abs(latest["middle"] - 100.0) < 1e-10
        assert abs(latest["lower"] - 100.0) < 1e-10

    def test_bands_surround_middle(self):
        closes = [100.0 + i % 5 for i in range(30)]
        result = compute_bollinger_bands(closes, 20)
        latest = result[-1]
        assert latest["upper"] is not None
        assert latest["upper"] > latest["middle"] > latest["lower"]

    def test_insufficient_data(self):
        closes = [100.0] * 10
        result = compute_bollinger_bands(closes, 20)
        assert all(r["upper"] is None for r in result)

    def test_middle_equals_sma(self):
        closes = [100.0 + i for i in range(25)]
        bb = compute_bollinger_bands(closes, 20)
        sma = compute_sma(closes, 20)
        for i in range(len(closes)):
            if bb[i]["middle"] is not None:
                assert abs(bb[i]["middle"] - sma[i]) < 1e-10

    def test_length_matches_input(self):
        closes = [100.0] * 30
        result = compute_bollinger_bands(closes, 20)
        assert len(result) == len(closes)
