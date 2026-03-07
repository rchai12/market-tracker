"""Tests for signal feedback loop: outcome evaluation, weight clamping, and config."""

from worker.tasks.signals.weight_optimizer import clamp_weights
from worker.tasks.signals.signal_generator import _default_weights, _get_weights


class TestOutcomeEvaluation:
    """Test correctness logic for signal outcome evaluation."""

    def test_bullish_correct_when_price_up(self):
        # Simulated: direction="bullish", price_change_pct > 0 → correct
        assert _is_correct("bullish", 0.05)

    def test_bullish_incorrect_when_price_down(self):
        assert not _is_correct("bullish", -0.03)

    def test_bearish_correct_when_price_down(self):
        assert _is_correct("bearish", -0.05)

    def test_bearish_incorrect_when_price_up(self):
        assert not _is_correct("bearish", 0.02)

    def test_flat_price_bullish_is_incorrect(self):
        # price_change_pct == 0 means no up movement → bullish is wrong
        assert not _is_correct("bullish", 0.0)

    def test_flat_price_bearish_is_incorrect(self):
        assert not _is_correct("bearish", 0.0)

    def test_price_change_calculation(self):
        signal_close = 100.0
        outcome_close = 105.0
        pct = (outcome_close - signal_close) / signal_close
        assert abs(pct - 0.05) < 1e-10


class TestWeightClamping:
    """Test the clamp_weights utility."""

    def test_preserves_sum_to_one(self):
        weights = {"a": 0.7, "b": 0.2, "c": 0.05, "d": 0.05}
        result = clamp_weights(weights, 0.05, 0.60)
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_respects_min_bound(self):
        weights = {"a": 0.01, "b": 0.33, "c": 0.33, "d": 0.33}
        result = clamp_weights(weights, 0.05, 0.60)
        assert all(v >= 0.049 for v in result.values())  # small float tolerance

    def test_respects_max_bound(self):
        weights = {"a": 0.90, "b": 0.04, "c": 0.03, "d": 0.03}
        result = clamp_weights(weights, 0.05, 0.60)
        assert all(v <= 0.601 for v in result.values())  # small float tolerance

    def test_default_weights_unchanged_when_within_bounds(self):
        weights = {"a": 0.40, "b": 0.25, "c": 0.20, "d": 0.15}
        result = clamp_weights(weights, 0.05, 0.60)
        for k in weights:
            assert abs(result[k] - weights[k]) < 0.001

    def test_equal_inputs_produce_equal_outputs(self):
        weights = {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
        result = clamp_weights(weights, 0.05, 0.60)
        values = list(result.values())
        assert all(abs(v - 0.25) < 0.001 for v in values)

    def test_extreme_imbalance(self):
        weights = {"a": 0.97, "b": 0.01, "c": 0.01, "d": 0.01}
        result = clamp_weights(weights, 0.05, 0.60)
        assert abs(sum(result.values()) - 1.0) < 0.001
        assert all(v >= 0.049 for v in result.values())
        assert all(v <= 0.601 for v in result.values())


class TestWeightLoading:
    """Test adaptive weight loading logic."""

    def test_default_weights_source(self):
        result = _default_weights()
        assert result["source"] == "default"
        total = sum(v for k, v in result.items() if k != "source")
        assert abs(total - 1.0) < 0.001

    def test_default_weights_values(self):
        result = _default_weights()
        assert result["sentiment_momentum"] == 0.40
        assert result["sentiment_volume"] == 0.25
        assert result["price_momentum"] == 0.20
        assert result["volume_anomaly"] == 0.15

    def test_get_weights_empty_map_returns_defaults(self):
        result = _get_weights({}, sector_id=1)
        assert result["source"] == "default"

    def test_get_weights_none_map_returns_defaults(self):
        result = _get_weights(None, sector_id=1)
        assert result["source"] == "default"

    def test_get_weights_sector_match(self):
        weights_map = {
            1: {"sentiment_momentum": 0.30, "sentiment_volume": 0.30,
                "price_momentum": 0.25, "volume_anomaly": 0.15, "source": "sector"},
        }
        result = _get_weights(weights_map, sector_id=1)
        assert result["source"] == "sector"
        assert result["sentiment_momentum"] == 0.30

    def test_get_weights_sector_miss_falls_to_global(self):
        weights_map = {
            None: {"sentiment_momentum": 0.35, "sentiment_volume": 0.25,
                   "price_momentum": 0.25, "volume_anomaly": 0.15, "source": "global"},
        }
        result = _get_weights(weights_map, sector_id=99)
        assert result["source"] == "global"

    def test_get_weights_no_global_falls_to_default(self):
        weights_map = {
            2: {"sentiment_momentum": 0.30, "sentiment_volume": 0.30,
                "price_momentum": 0.25, "volume_anomaly": 0.15, "source": "sector"},
        }
        result = _get_weights(weights_map, sector_id=99)
        assert result["source"] == "default"


class TestFeedbackConfig:
    """Test feedback loop configuration."""

    def test_default_config_values(self):
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test" * 16,
        )
        assert s.feedback_enabled is True
        assert s.feedback_min_samples == 50
        assert s.feedback_weight_min == 0.05
        assert s.feedback_weight_max == 0.60
        assert s.feedback_lookback_days == 90

    def test_feedback_windows_parsed(self):
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test" * 16,
            feedback_evaluation_windows="1,3,5",
        )
        assert s.feedback_windows_list == [1, 3, 5]

    def test_custom_windows(self):
        from app.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test" * 16,
            feedback_evaluation_windows="2,7",
        )
        assert s.feedback_windows_list == [2, 7]


class TestTaskRegistration:
    """Test that feedback tasks are properly registered."""

    def test_evaluate_outcomes_registered(self):
        from worker.tasks.signals.outcome_evaluator import evaluate_signal_outcomes

        assert evaluate_signal_outcomes.name == "worker.tasks.signals.outcome_evaluator.evaluate_signal_outcomes"

    def test_compute_weights_registered(self):
        from worker.tasks.signals.weight_optimizer import compute_adaptive_weights

        assert compute_adaptive_weights.name == "worker.tasks.signals.weight_optimizer.compute_adaptive_weights"


class TestBeatScheduleFeedback:
    """Test that feedback tasks are in the beat schedule."""

    def test_outcome_evaluation_in_schedule(self):
        from worker.beat_schedule import beat_schedule

        assert "evaluate-signal-outcomes" in beat_schedule

    def test_weight_computation_in_schedule(self):
        from worker.beat_schedule import beat_schedule

        assert "compute-adaptive-weights" in beat_schedule

    def test_outcome_evaluation_at_45(self):
        from worker.beat_schedule import beat_schedule

        schedule = beat_schedule["evaluate-signal-outcomes"]["schedule"]
        assert schedule.minute == {45}

    def test_weight_computation_at_4am(self):
        from worker.beat_schedule import beat_schedule

        schedule = beat_schedule["compute-adaptive-weights"]["schedule"]
        assert schedule.hour == {4}
        assert schedule.minute == {0}


# ── Test helpers ──


def _is_correct(direction: str, price_change_pct: float) -> bool:
    """Mirror the correctness logic from outcome_evaluator."""
    return (direction == "bullish" and price_change_pct > 0) or (
        direction == "bearish" and price_change_pct < 0
    )
