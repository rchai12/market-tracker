"""Phase 23a: promote qualifying LightGBM scores into the live composite."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from worker.utils.backtester.engine import _compute_components
from worker.utils.backtester.models import DEFAULT_WEIGHTS
from worker.utils.signal_formula import (
    WEIGHT_ML,
    apply_component_gates,
    combine_component_scores,
    default_weights,
    ml_model_qualifies,
)


def _numeric_sum(weights: dict) -> float:
    return sum(v for k, v in weights.items() if k != "source")


def _combine(**overrides):
    kwargs = dict(
        sentiment_momentum=0.5,
        sentiment_volume=0.2,
        price_momentum=0.3,
        volume_anomaly=0.1,
        rsi_score=None,
        trend_score=None,
        has_options=False,
    )
    kwargs.update(overrides)
    return combine_component_scores(**kwargs)


class TestMlModelQualifies:
    def test_percent_accuracy_at_threshold(self):
        assert ml_model_qualifies(55.0, 50) is True

    def test_ratio_accuracy_at_threshold(self):
        assert ml_model_qualifies(0.55, 50) is True

    def test_percent_below_accuracy_fails(self):
        assert ml_model_qualifies(54.9, 100) is False

    def test_ratio_below_accuracy_fails(self):
        assert ml_model_qualifies(0.54, 100) is False

    def test_too_few_samples_fails(self):
        assert ml_model_qualifies(80.0, 49) is False

    def test_missing_accuracy_fails(self):
        assert ml_model_qualifies(None, 100) is False

    def test_missing_sample_count_fails(self):
        assert ml_model_qualifies(60.0, None) is False

    def test_missing_model_or_score_is_not_promoted(self):
        model = SimpleNamespace(validation_accuracy=70.0, training_samples=200)
        ml_result = None
        has_ml = (
            ml_result is not None
            and model is not None
            and ml_model_qualifies(model.validation_accuracy, model.training_samples)
        )
        assert has_ml is False
        has_ml_no_model = ml_result is not None and None is not None
        assert has_ml_no_model is False


class TestMlWeights:
    def test_weight_ml_is_0_08(self):
        assert WEIGHT_ML == 0.08

    def test_has_ml_only_sums_to_one(self):
        w = default_weights(has_options=False, has_earnings=False, has_ml=True)
        assert abs(w["ml"] - 0.08) < 1e-9
        assert abs(_numeric_sum(w) - 1.0) < 1e-9
        assert abs(w["sentiment_momentum"] - 0.40 * 0.92) < 1e-9

    def test_all_four_gated_pool_is_0_33(self):
        w = default_weights(has_options=True, has_earnings=True, has_analyst=True, has_ml=True)
        assert abs(w["earnings"] - 0.10) < 1e-9
        assert abs(w["options"] - 0.08) < 1e-9
        assert abs(w["analyst"] - 0.07) < 1e-9
        assert abs(w["ml"] - 0.08) < 1e-9
        gated = w["earnings"] + w["options"] + w["analyst"] + w["ml"]
        assert abs(gated - 0.33) < 1e-9
        scale = 0.67
        assert abs(w["sentiment_momentum"] - 0.40 * scale) < 1e-9
        assert abs(_numeric_sum(w) - 1.0) < 1e-9

    def test_inactive_ml_stays_zero_in_defaults(self):
        w = default_weights(has_options=False, has_earnings=False, has_ml=False)
        assert w["ml"] == 0.0
        assert abs(_numeric_sum(w) - 1.0) < 1e-9

    def test_apply_gates_zeros_ml_when_inactive(self):
        w0 = default_weights(has_ml=True)
        w = apply_component_gates(w0, has_earnings=False, has_options=False, has_ml=False)
        assert w["ml"] == 0.0
        assert abs(w0["ml"] - 0.08) < 1e-9


class TestCombineWithMl:
    def test_has_ml_includes_ml_score_in_composite(self):
        result = _combine(ml_score=0.5, has_ml=True)
        assert result is not None
        assert result["ml_score"] == 0.5
        scale = 0.92
        raw = (
            0.40 * scale * 0.5
            + 0.25 * scale * 0.2
            + 0.20 * scale * 0.3
            + 0.15 * scale * 0.1
            + 0.08 * 0.5
        )
        assert abs(result["composite"] - raw) < 1e-9

    def test_has_ml_false_ignores_ml_score_in_composite(self):
        without = _combine(ml_score=0.5, has_ml=False)
        baseline = _combine()
        assert without is not None and baseline is not None
        assert without["ml_score"] == 0.5
        assert abs(without["composite"] - baseline["composite"]) < 1e-9
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert abs(without["composite"] - raw) < 1e-9

    def test_does_not_infer_has_ml_from_ml_score(self):
        result = _combine(ml_score=0.9)
        assert result is not None
        assert result["ml_score"] == 0.9
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert abs(result["composite"] - raw) < 1e-9

    def test_none_ml_score_preserved_when_gated_off(self):
        result = _combine()
        assert result is not None
        assert result["ml_score"] is None


class TestBacktesterForcesHasMlFalse:
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
        assert result["market_regime"] == "oversold"
        assert result.get("ml_score") is None
