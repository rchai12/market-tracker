"""Mutation-killing tests for worker/tasks/signals/signal_generator.py.

Focuses on weight constants, classification boundaries, weight lookup cascade,
and options weight redistribution.
"""

from worker.tasks.signals.signal_generator import (
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
    WEIGHT_OPTIONS,
    WEIGHT_PRICE_MOMENTUM,
    WEIGHT_PRICE_MOMENTUM_OPT,
    WEIGHT_RSI,
    WEIGHT_RSI_OPT,
    WEIGHT_SENTIMENT_MOMENTUM,
    WEIGHT_SENTIMENT_MOMENTUM_OPT,
    WEIGHT_SENTIMENT_VOLUME,
    WEIGHT_SENTIMENT_VOLUME_OPT,
    WEIGHT_TREND,
    WEIGHT_TREND_OPT,
    WEIGHT_VOLUME_ANOMALY,
    WEIGHT_VOLUME_ANOMALY_OPT,
    _get_weights,
    classify_direction,
    classify_strength,
)


class TestDefaultWeightsSum:
    def test_base_weights_sum_to_one(self):
        """Kill mutation: any weight constant changed."""
        total = (
            WEIGHT_SENTIMENT_MOMENTUM
            + WEIGHT_SENTIMENT_VOLUME
            + WEIGHT_PRICE_MOMENTUM
            + WEIGHT_VOLUME_ANOMALY
            + WEIGHT_RSI
            + WEIGHT_TREND
        )
        assert abs(total - 1.0) < 1e-10

    def test_options_weights_sum_to_one(self):
        """Kill mutation: options-enabled weights don't sum correctly."""
        total = (
            WEIGHT_SENTIMENT_MOMENTUM_OPT
            + WEIGHT_SENTIMENT_VOLUME_OPT
            + WEIGHT_PRICE_MOMENTUM_OPT
            + WEIGHT_VOLUME_ANOMALY_OPT
            + WEIGHT_RSI_OPT
            + WEIGHT_TREND_OPT
            + WEIGHT_OPTIONS
        )
        assert abs(total - 1.0) < 1e-10

    def test_options_weight_is_0_08(self):
        """Kill mutation: WEIGHT_OPTIONS changed."""
        assert WEIGHT_OPTIONS == 0.08

    def test_each_base_weight_correct(self):
        """Kill mutation: individual weight values."""
        assert WEIGHT_SENTIMENT_MOMENTUM == 0.30
        assert WEIGHT_SENTIMENT_VOLUME == 0.20
        assert WEIGHT_PRICE_MOMENTUM == 0.15
        assert WEIGHT_VOLUME_ANOMALY == 0.10
        assert WEIGHT_RSI == 0.15
        assert WEIGHT_TREND == 0.10


class TestClassifyDirectionBoundary:
    def test_at_exactly_0_01(self):
        """Kill mutation: `> 0.01` changed to `>= 0.01`."""
        assert classify_direction(0.01) == "neutral"
        assert classify_direction(0.0100001) == "bullish"

    def test_at_exactly_negative_0_01(self):
        """Kill mutation: `< -0.01` changed to `<= -0.01`."""
        assert classify_direction(-0.01) == "neutral"
        assert classify_direction(-0.0100001) == "bearish"

    def test_zero(self):
        assert classify_direction(0.0) == "neutral"


class TestClassifyStrengthBoundary:
    def test_at_exactly_strong_threshold(self):
        """Kill mutation: `> STRONG_THRESHOLD` changed to `>=`."""
        assert classify_strength(STRONG_THRESHOLD) == "moderate"
        assert classify_strength(STRONG_THRESHOLD + 0.0001) == "strong"

    def test_at_exactly_moderate_threshold(self):
        """Kill mutation: `> MODERATE_THRESHOLD` changed to `>=`."""
        assert classify_strength(MODERATE_THRESHOLD) == "weak"
        assert classify_strength(MODERATE_THRESHOLD + 0.0001) == "moderate"

    def test_negative_values(self):
        """Kill mutation: `abs(composite)` removed."""
        assert classify_strength(-0.7) == "strong"
        assert classify_strength(-0.4) == "moderate"
        assert classify_strength(-0.1) == "weak"


class TestWeightLookupCascade:
    def test_sector_specific_first(self):
        """Kill mutation: sector lookup order changed."""
        sector_weights = {
            "sentiment_momentum": 0.25, "sentiment_volume": 0.25,
            "price_momentum": 0.15, "volume_anomaly": 0.10,
            "rsi": 0.15, "trend": 0.10, "source": "sector",
        }
        global_weights = {
            "sentiment_momentum": 0.30, "sentiment_volume": 0.20,
            "price_momentum": 0.15, "volume_anomaly": 0.10,
            "rsi": 0.15, "trend": 0.10, "source": "global",
        }
        weights_map = {1: sector_weights, None: global_weights}
        result = _get_weights(weights_map, sector_id=1)
        assert result["source"] == "sector"

    def test_global_fallback(self):
        """Kill mutation: global key `None` not checked."""
        global_weights = {
            "sentiment_momentum": 0.30, "sentiment_volume": 0.20,
            "price_momentum": 0.15, "volume_anomaly": 0.10,
            "rsi": 0.15, "trend": 0.10, "source": "global",
        }
        weights_map = {None: global_weights}
        result = _get_weights(weights_map, sector_id=99)
        assert result["source"] == "global"

    def test_default_when_no_map(self):
        """Kill mutation: empty map falls through to defaults."""
        result = _get_weights({}, sector_id=1)
        assert result["source"] == "default"

    def test_default_when_none_map(self):
        """Kill mutation: None weights_map falls through to defaults."""
        result = _get_weights(None, sector_id=1)
        assert result["source"] == "default"
