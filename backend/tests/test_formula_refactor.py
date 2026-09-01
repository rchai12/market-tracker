"""Tests for Phase 21c signal formula refactor (regime multiplier, 4-component weights)."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from worker.tasks.signals.signal_generator import (
    WEIGHT_OPTIONS,
    WEIGHT_PRICE_MOMENTUM,
    WEIGHT_PRICE_MOMENTUM_OPT,
    WEIGHT_SENTIMENT_MOMENTUM,
    WEIGHT_SENTIMENT_MOMENTUM_OPT,
    WEIGHT_SENTIMENT_VOLUME,
    WEIGHT_SENTIMENT_VOLUME_OPT,
    WEIGHT_VOLUME_ANOMALY,
    WEIGHT_VOLUME_ANOMALY_OPT,
    _compute_composite_score,
    _default_weights,
    apply_regime_multiplier,
)
from worker.tasks.signals.weight_optimizer import _compute_sector_weights, _upsert_weights

NOW = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)


class TestApplyRegimeMultiplier:
    def test_rsi_oversold_dampens(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=0.5, trend_score=0.0)
        assert abs(adjusted - 0.34) < 1e-9
        assert regime == "oversold"

    def test_rsi_overbought_dampens_bullish(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=-0.5, trend_score=0.0)
        assert abs(adjusted - 0.34) < 1e-9
        assert regime == "overbought"

    def test_rsi_overbought_dampens_bearish(self):
        adjusted, regime = apply_regime_multiplier(-0.4, rsi_score=-0.5, trend_score=0.0)
        assert abs(adjusted - (-0.34)) < 1e-9
        assert regime == "overbought"

    def test_trend_confirms_bullish(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=0.0, trend_score=0.5)
        assert abs(adjusted - 0.46) < 1e-9
        assert regime == "trending_up"

    def test_trend_opposes_bearish(self):
        adjusted, regime = apply_regime_multiplier(-0.4, rsi_score=0.0, trend_score=0.5)
        assert abs(adjusted - (-0.34)) < 1e-9
        assert regime == "trending_up"

    def test_trend_confirms_bearish(self):
        adjusted, regime = apply_regime_multiplier(-0.4, rsi_score=0.0, trend_score=-0.5)
        assert abs(adjusted - (-0.46)) < 1e-9
        assert regime == "trending_down"

    def test_trend_opposes_bullish(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=0.0, trend_score=-0.5)
        assert abs(adjusted - 0.34) < 1e-9
        assert regime == "trending_down"

    def test_rsi_wins_priority_over_trend(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=0.5, trend_score=0.5)
        assert abs(adjusted - 0.34) < 1e-9
        assert regime == "oversold"

    def test_both_none_is_sideways(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=None, trend_score=None)
        assert adjusted == 0.4
        assert regime == "sideways"

    def test_weak_trend_neutral_rsi_is_sideways(self):
        adjusted, regime = apply_regime_multiplier(0.4, rsi_score=0.1, trend_score=0.2)
        assert adjusted == 0.4
        assert regime == "sideways"

    def test_zero_composite_sideways(self):
        adjusted, regime = apply_regime_multiplier(0.0, rsi_score=None, trend_score=None)
        assert adjusted == 0.0
        assert regime == "sideways"


class TestDefaultWeights:
    def test_base_rsi_trend_zero_and_sum_to_one(self):
        w = _default_weights(has_options=False)
        assert w["rsi"] == 0.0
        assert w["trend"] == 0.0
        predictive = (
            w["sentiment_momentum"] + w["sentiment_volume"] + w["price_momentum"] + w["volume_anomaly"]
        )
        assert abs(predictive - 1.0) < 1e-9
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9

    def test_options_enabled_sums_to_one(self):
        w = _default_weights(has_options=True)
        assert w["options"] == 0.08
        assert w["rsi"] == 0.0
        assert w["trend"] == 0.0
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9

    def test_weight_constants_sum_to_one(self):
        assert abs(
            WEIGHT_SENTIMENT_MOMENTUM
            + WEIGHT_SENTIMENT_VOLUME
            + WEIGHT_PRICE_MOMENTUM
            + WEIGHT_VOLUME_ANOMALY
            - 1.0
        ) < 1e-9
        assert abs(
            WEIGHT_SENTIMENT_MOMENTUM_OPT
            + WEIGHT_SENTIMENT_VOLUME_OPT
            + WEIGHT_PRICE_MOMENTUM_OPT
            + WEIGHT_VOLUME_ANOMALY_OPT
            + WEIGHT_OPTIONS
            - 1.0
        ) < 1e-9


def _score_row(**overrides):
    base = dict(
        sentiment_score=0.5,
        price_score=0.2,
        volume_score=0.1,
        options_score=None,
        direction="bullish",
        is_correct=True,
        price_change_pct=0.05,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestWeightOptimizerComponents:
    def test_rsi_and_trend_not_in_result(self):
        rows = [_score_row() for _ in range(3)]
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        session.execute = AsyncMock(return_value=result_mock)

        with patch("worker.tasks.signals.weight_optimizer.settings") as mock_settings:
            mock_settings.feedback_min_samples = 2
            mock_settings.options_flow_enabled = False
            mock_settings.feedback_weight_min = 0.05
            mock_settings.feedback_weight_max = 0.60
            result = asyncio.run(_compute_sector_weights(session, 1, NOW))

        assert result is not None
        assert "rsi" not in result
        assert "trend" not in result
        assert "earnings" not in result
        assert "sentiment_momentum" in result
        assert "volume_anomaly" in result

    def test_upsert_always_writes_rsi_trend_zero(self):
        captured = {}

        class FakeInsert:
            excluded = MagicMock()

            def values(self, **kwargs):
                captured.update(kwargs)
                return self

            def on_conflict_on_constraint(self, _name):
                return self

            def do_update(self, set_=None):
                return self

        session = AsyncMock()
        weights = {
            "sentiment_momentum": 0.40,
            "sentiment_volume": 0.25,
            "price_momentum": 0.20,
            "volume_anomaly": 0.15,
            "sample_count": 50,
            "accuracy_pct": 55.0,
        }
        with patch("worker.tasks.signals.weight_optimizer.pg_insert", return_value=FakeInsert()):
            asyncio.run(_upsert_weights(session, 1, weights))

        assert captured["rsi"] == 0.0
        assert captured["trend"] == 0.0
        assert "earnings" not in captured


def _patch_components(**returns):
    defaults = {
        "calc_sentiment_momentum": 0.5,
        "calc_sentiment_volume": 0.2,
        "calc_price_momentum": 0.3,
        "calc_volume_anomaly": 0.1,
        "calc_rsi_score": None,
        "calc_trend_score": None,
        "calc_options_score": None,
        "get_recent_article_count": 2,
    }
    defaults.update(returns)
    patches = []
    for name, value in defaults.items():
        mock = AsyncMock(return_value=value)
        patches.append(patch(f"worker.tasks.signals.signal_generator.{name}", mock))
    return patches


class TestComputeCompositeScoreRegime:
    def test_regime_set_when_rsi_and_trend_computed(self):
        patches = _patch_components(calc_rsi_score=0.2, calc_trend_score=0.2)

        async def _run():
            for p in patches:
                p.start()
            try:
                return await _compute_composite_score(AsyncMock(), 1, NOW)
            finally:
                for p in patches:
                    p.stop()

        result = asyncio.run(_run())
        assert result is not None
        assert result["market_regime"] in (
            "overbought",
            "oversold",
            "trending_up",
            "trending_down",
            "sideways",
        )
        assert result["market_regime"] != "unknown"

    def test_rsi_extreme_dampens_composite_15_percent(self):
        patches = _patch_components(calc_rsi_score=0.5, calc_trend_score=0.0)

        async def _run():
            for p in patches:
                p.start()
            try:
                return await _compute_composite_score(AsyncMock(), 1, NOW)
            finally:
                for p in patches:
                    p.stop()

        result = asyncio.run(_run())
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert result is not None
        assert abs(result["composite"] - raw * 0.85) < 1e-9
        assert result["market_regime"] == "oversold"

    def test_trend_confirm_boosts_composite_15_percent(self):
        patches = _patch_components(calc_rsi_score=0.0, calc_trend_score=0.5)

        async def _run():
            for p in patches:
                p.start()
            try:
                return await _compute_composite_score(AsyncMock(), 1, NOW)
            finally:
                for p in patches:
                    p.stop()

        result = asyncio.run(_run())
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert result is not None
        assert abs(result["composite"] - raw * 1.15) < 1e-9
        assert result["market_regime"] == "trending_up"

    def test_none_rsi_trend_sideways_no_multiplier(self):
        patches = _patch_components(calc_rsi_score=None, calc_trend_score=None)

        async def _run():
            for p in patches:
                p.start()
            try:
                return await _compute_composite_score(AsyncMock(), 1, NOW)
            finally:
                for p in patches:
                    p.stop()

        result = asyncio.run(_run())
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert result is not None
        assert abs(result["composite"] - raw) < 1e-9
        assert result["market_regime"] == "sideways"
