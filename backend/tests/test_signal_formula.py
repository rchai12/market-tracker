"""Tests for the shared live/backtest signal formula module."""

from datetime import date
from unittest.mock import patch

from worker.utils.backtester.engine import _compute_components
from worker.utils.backtester.models import DEFAULT_WEIGHTS
from worker.utils.signal_formula import (
    apply_component_gates,
    combine_component_scores,
    default_weights,
    resolve_weights,
)


class TestApplyComponentGates:
    def test_inactive_earnings_renormalizes_predictive_keys(self):
        adaptive = {
            "sentiment_momentum": 0.33,
            "sentiment_volume": 0.21,
            "price_momentum": 0.16,
            "volume_anomaly": 0.12,
            "earnings": 0.10,
            "options": 0.08,
            "rsi": 0.0,
            "trend": 0.0,
            "source": "sector",
        }
        w = apply_component_gates(adaptive, has_earnings=False, has_options=False)
        assert w["earnings"] == 0.0
        assert w["options"] == 0.0
        assert w["rsi"] == 0.0
        assert w["trend"] == 0.0
        predictive = (
            w["sentiment_momentum"]
            + w["sentiment_volume"]
            + w["price_momentum"]
            + w["volume_anomaly"]
        )
        assert abs(predictive - 1.0) < 1e-9
        assert w["source"] == "sector"
        # Original map must not be mutated (shared across stocks).
        assert adaptive["earnings"] == 0.10

    def test_active_gates_are_identity_when_already_normalized(self):
        w0 = default_weights(has_options=True, has_earnings=True)
        w = apply_component_gates(w0, has_earnings=True, has_options=True)
        assert abs(w["earnings"] - 0.10) < 1e-9
        assert abs(w["options"] - 0.08) < 1e-9
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9


class TestResolveWeights:
    def test_does_not_mutate_cached_map_when_gating(self):
        cached = {
            1: {
                "sentiment_momentum": 0.36,
                "sentiment_volume": 0.22,
                "price_momentum": 0.18,
                "volume_anomaly": 0.14,
                "earnings": 0.10,
                "options": 0.0,
                "source": "sector",
            }
        }
        w = resolve_weights(cached, sector_id=1, has_earnings=False, has_options=False)
        assert w["earnings"] == 0.0
        assert abs(w["sentiment_momentum"] + w["sentiment_volume"] + w["price_momentum"] + w["volume_anomaly"] - 1.0) < 1e-9
        assert cached[1]["earnings"] == 0.10


class TestCombineComponentScores:
    def test_zero_earnings_is_active_not_missing(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            earnings_score=0.0,
            options_score=None,
            has_options=False,
        )
        assert result is not None
        assert result["earnings_score"] == 0.0
        assert result["options_score"] is None
        raw = 0.36 * 0.5 + 0.22 * 0.2 + 0.18 * 0.3 + 0.14 * 0.1 + 0.10 * 0.0
        assert abs(result["composite"] - raw) < 1e-9

    def test_none_earnings_uses_base_weights(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            earnings_score=None,
            has_options=False,
        )
        assert result is not None
        assert result["earnings_score"] is None
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert abs(result["composite"] - raw) < 1e-9

    def test_regime_multiplier_applied(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=0.5,
            trend_score=0.0,
            has_options=False,
        )
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert result is not None
        assert abs(result["composite"] - raw * 0.85) < 1e-9
        assert result["market_regime"] == "oversold"

    def test_no_inputs_returns_none(self):
        assert (
            combine_component_scores(
                sentiment_momentum=None,
                sentiment_volume=None,
                price_momentum=None,
                volume_anomaly=None,
                rsi_score=None,
                trend_score=None,
            )
            is None
        )


class TestBacktesterUsesLiveFormula:
    def test_technical_mode_applies_regime_not_additive_rsi(self):
        """Old backtester weighted RSI at 0.30; live formula only uses it as ×0.85."""
        with (
            patch(
                "worker.utils.backtester.engine.compute_price_momentum_from_closes",
                return_value=0.5,
            ),
            patch(
                "worker.utils.backtester.engine.compute_volume_anomaly_from_data",
                return_value=0.0,
            ),
            patch(
                "worker.utils.backtester.engine.compute_rsi_score_from_closes",
                return_value=0.5,
            ),
            patch(
                "worker.utils.backtester.engine.compute_trend_score_from_closes",
                return_value=0.0,
            ),
        ):
            result = _compute_components(
                closes=[100.0] * 60,
                volumes=[1_000_000] * 60,
                current_date=date(2026, 1, 15),
                mode="technical",
                weights=DEFAULT_WEIGHTS,
                sentiment_data=None,
            )
        assert result is not None
        # Live: 0.20 * 0.5 = 0.10, then oversold × 0.85 → 0.085
        assert abs(result["composite"] - 0.085) < 1e-9
        assert result["market_regime"] == "oversold"
        # Old additive formula would have been 0.30*0.5 + 0.30*0.5 = 0.30
        assert abs(result["composite"] - 0.30) > 0.1
