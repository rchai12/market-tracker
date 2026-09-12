"""Phase 23: ML + insider both gated into the composite, weights still sum to 1.0."""

from datetime import date
from unittest.mock import patch

from worker.utils.backtester.engine import _compute_components
from worker.utils.backtester.models import DEFAULT_WEIGHTS
from worker.utils.signal_formula import (
    WEIGHT_INSIDER,
    WEIGHT_ML,
    combine_component_scores,
    default_weights,
)


def _numeric_sum(weights: dict) -> float:
    return sum(v for k, v in weights.items() if k != "source")


class TestInsiderAndMlWeights:
    def test_weight_insider_is_0_08(self):
        assert WEIGHT_INSIDER == 0.08
        assert WEIGHT_ML == 0.08

    def test_all_five_gated_pool_is_0_41(self):
        w = default_weights(
            has_options=True,
            has_earnings=True,
            has_analyst=True,
            has_ml=True,
            has_insider=True,
        )
        gated = w["earnings"] + w["options"] + w["analyst"] + w["ml"] + w["insider"]
        assert abs(gated - 0.41) < 1e-9
        assert abs(w["sentiment_momentum"] - 0.40 * 0.59) < 1e-9
        assert abs(_numeric_sum(w) - 1.0) < 1e-9

    def test_insider_only_sums_to_one(self):
        w = default_weights(has_insider=True)
        assert abs(w["insider"] - 0.08) < 1e-9
        assert abs(_numeric_sum(w) - 1.0) < 1e-9


class TestCombineMlAndInsider:
    def test_both_active_in_composite(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            ml_score=0.5,
            has_ml=True,
            insider_score=0.5,
            has_options=False,
        )
        assert result is not None
        assert result["insider_score"] == 0.5
        assert result["ml_score"] == 0.5
        scale = 0.84  # 1 - (0.08 ml + 0.08 insider)
        raw = (
            0.40 * scale * 0.5
            + 0.25 * scale * 0.2
            + 0.20 * scale * 0.3
            + 0.15 * scale * 0.1
            + 0.08 * 0.5
            + 0.08 * 0.5
        )
        assert abs(result["composite"] - raw) < 1e-9

    def test_none_insider_excluded(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            insider_score=None,
            has_options=False,
        )
        assert result is not None
        assert result["insider_score"] is None
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert abs(result["composite"] - raw) < 1e-9


class TestBacktesterForcesInsiderOff:
    def test_technical_mode_composite_unchanged(self):
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
        assert abs(result["composite"] - 0.085) < 1e-9
        assert result.get("insider_score") is None
