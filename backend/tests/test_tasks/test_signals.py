"""Tests for signal generation scoring and alert matching logic."""

import math
from unittest.mock import MagicMock

from worker.tasks.signals.signal_generator import (
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
    _build_reasoning,
    classify_direction,
    classify_strength,
)


class TestClassifyDirection:
    def test_bullish(self):
        assert classify_direction(0.5) == "bullish"
        assert classify_direction(0.02) == "bullish"

    def test_bearish(self):
        assert classify_direction(-0.5) == "bearish"
        assert classify_direction(-0.02) == "bearish"

    def test_neutral(self):
        assert classify_direction(0.0) == "neutral"
        assert classify_direction(0.005) == "neutral"
        assert classify_direction(-0.005) == "neutral"


class TestClassifyStrength:
    def test_strong(self):
        assert classify_strength(0.7) == "strong"
        assert classify_strength(-0.65) == "strong"

    def test_moderate(self):
        assert classify_strength(0.4) == "moderate"
        assert classify_strength(-0.5) == "moderate"

    def test_weak(self):
        assert classify_strength(0.1) == "weak"
        assert classify_strength(-0.2) == "weak"
        assert classify_strength(0.0) == "weak"

    def test_thresholds_exact(self):
        # At exact threshold, should be one step below
        assert classify_strength(STRONG_THRESHOLD) == "moderate"
        assert classify_strength(MODERATE_THRESHOLD) == "weak"
        # Just above threshold
        assert classify_strength(STRONG_THRESHOLD + 0.001) == "strong"
        assert classify_strength(MODERATE_THRESHOLD + 0.001) == "moderate"


class TestBuildReasoning:
    def test_basic_reasoning(self):
        score_data = {
            "composite": 0.45,
            "sentiment_momentum": 0.1,
            "sentiment_volume": 0.05,
            "price_momentum": 0.1,
            "volume_anomaly": 0.1,
            "article_count": 3,
        }
        result = _build_reasoning("XOM", score_data, "bullish", "moderate")
        assert "XOM" in result
        assert "moderate" in result
        assert "bullish" in result
        assert "0.450" in result
        assert "3 articles" in result

    def test_strong_sentiment_included(self):
        score_data = {
            "composite": 0.7,
            "sentiment_momentum": 0.5,
            "sentiment_volume": 0.2,
            "price_momentum": 0.3,
            "volume_anomaly": 0.4,
            "article_count": 10,
        }
        result = _build_reasoning("JPM", score_data, "bullish", "strong")
        assert "positive" in result  # sentiment momentum > 0.3
        assert "upward" in result  # price momentum > 0.2
        assert "above" in result  # volume anomaly > 0.3

    def test_negative_sentiment(self):
        score_data = {
            "composite": -0.5,
            "sentiment_momentum": -0.4,
            "sentiment_volume": -0.2,
            "price_momentum": -0.3,
            "volume_anomaly": -0.4,
            "article_count": 5,
        }
        result = _build_reasoning("BAC", score_data, "bearish", "moderate")
        assert "negative" in result
        assert "downward" in result
        assert "below" in result

    def test_zero_articles(self):
        score_data = {
            "composite": 0.2,
            "sentiment_momentum": 0.0,
            "sentiment_volume": 0.0,
            "price_momentum": 0.1,
            "volume_anomaly": 0.1,
            "article_count": 0,
        }
        result = _build_reasoning("CVX", score_data, "bullish", "weak")
        assert "articles" not in result


class TestAlertConfigMatching:
    """Test the alert config matching logic from alert_dispatcher."""

    def test_strength_ordering(self):
        from worker.tasks.signals.alert_dispatcher import STRENGTH_ORDER

        assert STRENGTH_ORDER["weak"] < STRENGTH_ORDER["moderate"]
        assert STRENGTH_ORDER["moderate"] < STRENGTH_ORDER["strong"]

    def test_channel_expansion(self):
        from worker.tasks.signals.alert_dispatcher import _get_channels

        assert _get_channels("both") == ["discord", "email"]
        assert _get_channels("discord") == ["discord"]
        assert _get_channels("email") == ["email"]


class TestScoringMath:
    """Test the mathematical properties of the scoring functions."""

    def test_tanh_scaling_price_momentum(self):
        # 10% price increase -> tanh(0.1 * 5) = tanh(0.5) ≈ 0.46
        pct_change = 0.10
        result = math.tanh(pct_change * 5)
        assert 0.45 < result < 0.48

    def test_tanh_scaling_large_move(self):
        # 50% price increase -> tanh(2.5) ≈ 0.99
        pct_change = 0.50
        result = math.tanh(pct_change * 5)
        assert result > 0.98

    def test_exponential_decay(self):
        # Recent scores should have higher weight than older ones
        half_life = 6
        decay_rate = math.log(2) / half_life

        weight_1h = math.exp(-decay_rate * 1)  # 1 hour ago
        weight_6h = math.exp(-decay_rate * 6)  # 6 hours ago (half-life)
        weight_12h = math.exp(-decay_rate * 12)  # 12 hours ago

        assert weight_1h > weight_6h
        assert weight_6h > weight_12h
        # At half-life, weight should be ~0.5
        assert abs(weight_6h - 0.5) < 0.01
        # At 2x half-life, weight should be ~0.25
        assert abs(weight_12h - 0.25) < 0.01

    def test_composite_weights_sum_to_one(self):
        from worker.tasks.signals.signal_generator import (
            WEIGHT_PRICE_MOMENTUM,
            WEIGHT_SENTIMENT_MOMENTUM,
            WEIGHT_SENTIMENT_VOLUME,
            WEIGHT_VOLUME_ANOMALY,
        )

        total = (
            WEIGHT_SENTIMENT_MOMENTUM
            + WEIGHT_SENTIMENT_VOLUME
            + WEIGHT_PRICE_MOMENTUM
            + WEIGHT_VOLUME_ANOMALY
        )
        assert abs(total - 1.0) < 0.001

    def test_volume_anomaly_ratio(self):
        # Volume ratio of 2x -> tanh(1) ≈ 0.76
        ratio = 2.0
        magnitude = math.tanh(ratio - 1.0)
        assert 0.75 < magnitude < 0.77

        # Normal volume -> tanh(0) = 0
        ratio = 1.0
        magnitude = math.tanh(ratio - 1.0)
        assert magnitude == 0.0
