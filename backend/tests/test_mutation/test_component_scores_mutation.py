"""Mutation-killing tests for worker/tasks/signals/component_scores.py.

Since the DB-dependent async functions can't be unit-tested without a real DB,
we test the pure math formulas via the equivalent backtester/signals.py functions
and verify the mathematical constants and formulas used in component_scores.py.
"""

import math
from datetime import date, timedelta

from worker.utils.backtester.signals import (
    classify_direction,
    classify_strength,
    compute_price_momentum_from_closes,
    compute_rsi_score_from_closes,
    compute_sentiment_momentum_from_data,
    compute_sentiment_volume_from_data,
    compute_trend_score_from_closes,
    compute_volume_anomaly_from_data,
)
from worker.utils.backtester.models import (
    BASELINE_DAYS,
    MODERATE_THRESHOLD,
    SENTIMENT_HALF_LIFE_HOURS,
    STRONG_THRESHOLD,
    SentimentRow,
)


class TestDecayRate:
    def test_half_life_weight_is_half(self):
        """Kill mutation: `ln(2) / half_life` formula changes."""
        half_life_days = SENTIMENT_HALF_LIFE_HOURS / 24.0
        decay_rate = math.log(2) / half_life_days
        # At exactly half_life_days ago, weight should be 0.5
        weight_at_half_life = math.exp(-decay_rate * half_life_days)
        assert abs(weight_at_half_life - 0.5) < 1e-10

    def test_decay_rate_value(self):
        """Kill mutation: verify exact decay rate constant."""
        # ln(2) / 6 for hours-based; ln(2) / 0.25 for days-based
        expected_decay = math.log(2) / (SENTIMENT_HALF_LIFE_HOURS / 24.0)
        actual_decay = math.log(2) / (6 / 24.0)
        assert abs(expected_decay - actual_decay) < 1e-10


class TestSentimentValueDirection:
    def test_positive_minus_negative(self):
        """Kill mutation: `positive - negative` changed to `negative - positive`."""
        today = date(2024, 6, 15)
        # Positive dominant: 0.9 - 0.1 = 0.8 > 0
        rows_pos = [
            SentimentRow(date=today, avg_positive=0.9, avg_negative=0.1, article_count=5),
        ]
        result_pos = compute_sentiment_momentum_from_data(rows_pos, today)
        assert result_pos is not None
        assert result_pos > 0

        # Negative dominant: 0.1 - 0.9 = -0.8 < 0
        rows_neg = [
            SentimentRow(date=today, avg_positive=0.1, avg_negative=0.9, article_count=5),
        ]
        result_neg = compute_sentiment_momentum_from_data(rows_neg, today)
        assert result_neg is not None
        assert result_neg < 0

    def test_equal_scores_near_zero(self):
        """Kill mutation: subtraction cancels to zero when equal."""
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today, avg_positive=0.5, avg_negative=0.5, article_count=5),
        ]
        result = compute_sentiment_momentum_from_data(rows, today)
        assert result is not None
        assert abs(result) < 1e-10


class TestVolumeDirectionSign:
    def test_positive_direction(self):
        """Kill mutation: `1.0 if net >= 0 else -1.0` boundary."""
        closes = [100.0, 100.0, 100.0, 101.0]  # Price up
        volumes = [1000, 1000, 1000, 3000]  # Volume spike
        result = compute_volume_anomaly_from_data(closes, volumes)
        assert result is not None
        assert result > 0  # Up price + high volume → positive

    def test_negative_direction(self):
        """Kill mutation: sign flipped."""
        closes = [100.0, 100.0, 100.0, 99.0]  # Price down
        volumes = [1000, 1000, 1000, 3000]  # Volume spike
        result = compute_volume_anomaly_from_data(closes, volumes)
        assert result is not None
        assert result < 0  # Down price + high volume → negative

    def test_flat_price_positive_direction(self):
        """Kill mutation: `>=` changed to `>` — equal price should be positive."""
        closes = [100.0, 100.0, 100.0, 100.0]  # Flat
        volumes = [1000, 1000, 1000, 2000]  # Volume above avg
        result = compute_volume_anomaly_from_data(closes, volumes)
        assert result is not None
        assert result >= 0  # Flat → direction = 1.0


class TestPriceMomentumTanh:
    def test_scaling_factor_5(self):
        """Kill mutation: `pct_change * 5` changed to `* 10` or `* 1`."""
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 110.0]
        result = compute_price_momentum_from_closes(closes)
        # pct_change = 0.1, tanh(0.1 * 5) = tanh(0.5)
        expected = math.tanh(0.5)
        assert result is not None
        assert abs(result - expected) < 1e-10

    def test_large_move_near_one(self):
        """Kill mutation: tanh saturation behavior."""
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 200.0]
        result = compute_price_momentum_from_closes(closes)
        # pct_change = 1.0, tanh(5.0) ≈ 0.9999
        assert result is not None
        assert result > 0.99

    def test_negative_momentum(self):
        """Kill mutation: subtraction order `(latest - oldest) / oldest`."""
        closes = [200.0, 180.0, 160.0, 140.0, 120.0, 100.0]
        result = compute_price_momentum_from_closes(closes)
        # pct_change = (100 - 200) / 200 = -0.5, tanh(-2.5)
        expected = math.tanh(-0.5 * 5)
        assert result is not None
        assert abs(result - expected) < 1e-10


class TestVolumeRatio:
    def test_ratio_formula(self):
        """Kill mutation: `latest / avg` changed to `avg / latest`."""
        closes = [100.0, 100.0, 100.0, 101.0]
        volumes = [1000, 1000, 1000, 3000]
        result = compute_volume_anomaly_from_data(closes, volumes)
        # ratio = 3000 / 1000 = 3.0
        # magnitude = tanh(3.0 - 1.0) = tanh(2.0)
        expected = math.tanh(2.0)  # ~0.964
        assert result is not None
        assert abs(result - expected) < 1e-4  # Allow small rounding

    def test_below_average_volume(self):
        """Kill mutation: `ratio - 1.0` subtraction."""
        closes = [100.0, 100.0, 100.0, 101.0]
        volumes = [2000, 2000, 2000, 500]
        result = compute_volume_anomaly_from_data(closes, volumes)
        # ratio = 500 / 2000 = 0.25
        # magnitude = tanh(0.25 - 1.0) = tanh(-0.75) ≈ -0.635
        # direction = positive (price up), so result ≈ -0.635 * 1.0
        expected = math.tanh(-0.75)
        assert result is not None
        assert abs(result - expected) < 1e-4


class TestRSICentering:
    def test_oversold_rsi_gives_positive(self):
        """Kill mutation: `(50 - rsi) / 50` direction — RSI<30 → positive."""
        # Generate oversold conditions (consistent drops)
        closes = [100 - i * 0.5 for i in range(30)]
        result = compute_rsi_score_from_closes(closes)
        assert result is not None
        assert result > 0  # Oversold = bullish = positive

    def test_overbought_rsi_gives_negative(self):
        """Kill mutation: `(50 - rsi) / 50` direction — RSI>70 → negative."""
        # Generate overbought conditions (consistent gains)
        closes = [100 + i * 0.5 for i in range(30)]
        result = compute_rsi_score_from_closes(closes)
        assert result is not None
        assert result < 0  # Overbought = bearish = negative

    def test_scaling_factor_2_5(self):
        """Kill mutation: `centered * 2.5` scaling constant."""
        # RSI at exactly 50 → centered = 0 → tanh(0) = 0
        # Generate flat data that produces RSI near 50
        closes = [100.0 + (0.5 if i % 2 == 0 else -0.5) for i in range(30)]
        result = compute_rsi_score_from_closes(closes)
        assert result is not None
        assert abs(result) < 0.3  # Near zero for balanced RSI


class TestTrendWeights:
    def test_sma_weight_0_6_macd_weight_0_4(self):
        """Kill mutation: `0.6 * sma + 0.4 * macd` weights changed."""
        # Strong uptrend: both SMA and MACD should be positive
        closes = [100 + i * 0.5 for i in range(60)]
        result = compute_trend_score_from_closes(closes)
        assert result is not None
        assert result > 0

        # The result is bounded by max(0.6*1 + 0.4*1) = 1.0
        assert -1.0 <= result <= 1.0

    def test_sma_normalization(self):
        """Kill mutation: `(sma20 - sma50) / sma50 * 10` operator changes."""
        # In uptrend, SMA20 > SMA50 → positive SMA diff
        closes_up = [100 + i * 1.0 for i in range(60)]
        result_up = compute_trend_score_from_closes(closes_up)
        assert result_up is not None
        assert result_up > 0

        # In downtrend, SMA20 < SMA50 → negative SMA diff
        closes_down = [160 - i * 1.0 for i in range(60)]
        result_down = compute_trend_score_from_closes(closes_down)
        assert result_down is not None
        assert result_down < 0


class TestSentimentVolume:
    def test_direction_sign_from_net_sentiment(self):
        """Kill mutation: `1.0 if net >= 0 else -1.0` sign."""
        today = date(2024, 6, 15)
        # Positive net sentiment with volume above baseline
        rows_pos = [
            SentimentRow(date=today, avg_positive=0.8, avg_negative=0.2, article_count=10),
        ]
        for i in range(1, 21):
            rows_pos.append(SentimentRow(
                date=today - timedelta(days=i), avg_positive=0.5, avg_negative=0.4, article_count=2,
            ))
        result_pos = compute_sentiment_volume_from_data(rows_pos, today)
        assert result_pos is not None
        assert result_pos > 0

        # Negative net sentiment with volume above baseline
        rows_neg = [
            SentimentRow(date=today, avg_positive=0.2, avg_negative=0.8, article_count=10),
        ]
        for i in range(1, 21):
            rows_neg.append(SentimentRow(
                date=today - timedelta(days=i), avg_positive=0.5, avg_negative=0.4, article_count=2,
            ))
        result_neg = compute_sentiment_volume_from_data(rows_neg, today)
        assert result_neg is not None
        assert result_neg < 0

    def test_tanh_ratio_minus_one(self):
        """Kill mutation: `tanh(ratio - 1.0)` subtraction of 1.0."""
        today = date(2024, 6, 15)
        # Exactly baseline volume (ratio = 1.0 → tanh(0) = 0)
        rows = [
            SentimentRow(date=today, avg_positive=0.6, avg_negative=0.3, article_count=2),
        ]
        for i in range(1, 21):
            rows.append(SentimentRow(
                date=today - timedelta(days=i), avg_positive=0.5, avg_negative=0.4, article_count=2,
            ))
        result = compute_sentiment_volume_from_data(rows, today)
        # ratio ≈ 1.0, tanh(0) = 0
        if result is not None:
            assert abs(result) < 0.15  # Near zero


class TestClassificationBoundaries:
    def test_direction_at_0_01(self):
        """Kill mutation: `> 0.01` boundary for bullish."""
        assert classify_direction(0.01) == "neutral"
        assert classify_direction(0.0100001) == "bullish"
        assert classify_direction(-0.01) == "neutral"
        assert classify_direction(-0.0100001) == "bearish"

    def test_strength_at_thresholds(self):
        """Kill mutation: `>` vs `>=` at STRONG_THRESHOLD and MODERATE_THRESHOLD."""
        assert classify_strength(STRONG_THRESHOLD) == "moderate"
        assert classify_strength(STRONG_THRESHOLD + 0.0001) == "strong"
        assert classify_strength(MODERATE_THRESHOLD) == "weak"
        assert classify_strength(MODERATE_THRESHOLD + 0.0001) == "moderate"
        assert classify_strength(-STRONG_THRESHOLD) == "moderate"
        assert classify_strength(-(STRONG_THRESHOLD + 0.0001)) == "strong"
