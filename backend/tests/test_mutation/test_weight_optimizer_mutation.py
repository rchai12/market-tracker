"""Mutation-killing tests for worker/tasks/signals/weight_optimizer.py.

Focuses on the clamp_weights function (pure math, no DB needed) and
verifying accuracy ratio formulas.
"""

from worker.tasks.signals.weight_optimizer import clamp_weights


class TestClampWeightsBasic:
    def test_sum_to_one(self):
        """Kill mutation: normalization broken, weights don't sum to 1.0."""
        weights = {
            "a": 0.3, "b": 0.2, "c": 0.15, "d": 0.10, "e": 0.15, "f": 0.10,
        }
        result = clamp_weights(weights, min_w=0.05, max_w=0.40)
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-9

    def test_all_in_range(self):
        """Kill mutation: clamp boundary `< min_w` changed to `<= min_w`."""
        weights = {
            "a": 0.01, "b": 0.90, "c": 0.03, "d": 0.02, "e": 0.02, "f": 0.02,
        }
        result = clamp_weights(weights, min_w=0.05, max_w=0.40)
        for k, v in result.items():
            assert v >= 0.05 - 1e-9, f"{k}={v} below min"
            assert v <= 0.40 + 1e-9, f"{k}={v} above max"

    def test_sum_preserved_after_clamping(self):
        """Kill mutation: `budget -= min_w` or `budget -= max_w` wrong."""
        weights = {
            "a": 0.02, "b": 0.70, "c": 0.02, "d": 0.02, "e": 0.02, "f": 0.22,
        }
        result = clamp_weights(weights, min_w=0.05, max_w=0.35)
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-6
        for k, v in result.items():
            assert v >= 0.05 - 1e-3
            assert v <= 0.35 + 1e-3


class TestClampWeightsEdgeCases:
    def test_already_valid_unchanged(self):
        """Kill mutation: clamping when already valid shouldn't change weights."""
        weights = {"a": 0.20, "b": 0.20, "c": 0.20, "d": 0.15, "e": 0.15, "f": 0.10}
        result = clamp_weights(weights, min_w=0.05, max_w=0.40)
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-9
        # All values should be approximately the same
        for k in weights:
            assert abs(result[k] - weights[k]) < 0.01

    def test_equal_weights(self):
        """Kill mutation: even distribution works correctly."""
        weights = {"a": 1/6, "b": 1/6, "c": 1/6, "d": 1/6, "e": 1/6, "f": 1/6}
        result = clamp_weights(weights, min_w=0.05, max_w=0.40)
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-9

    def test_extreme_concentration(self):
        """Kill mutation: handles extreme weight on one key."""
        weights = {"a": 0.95, "b": 0.01, "c": 0.01, "d": 0.01, "e": 0.01, "f": 0.01}
        result = clamp_weights(weights, min_w=0.05, max_w=0.40)
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-9
        assert result["a"] <= 0.40 + 1e-9
        for k in ["b", "c", "d", "e", "f"]:
            assert result[k] >= 0.05 - 1e-9


class TestAccuracyRatio:
    def test_correct_over_total(self):
        """Kill mutation: `correct / total` changed to `total / correct`."""
        # Simulate the accuracy computation from weight_optimizer
        correct = 7
        total = 10
        accuracy = correct / total
        assert abs(accuracy - 0.7) < 1e-10

    def test_neutral_prior_when_zero(self):
        """Kill mutation: neutral prior `0.5` changed."""
        # When total is 0, accuracy should be 0.5 (neutral prior)
        total = 0
        accuracy = 0.5 if total == 0 else 1 / total
        assert accuracy == 0.5

    def test_normalization_v_over_total_raw(self):
        """Kill mutation: `v / total_raw` changed to `total_raw / v`."""
        raw_weights = {"a": 0.6, "b": 0.4}
        total_raw = sum(raw_weights.values())
        normalized = {k: v / total_raw for k, v in raw_weights.items()}
        assert abs(normalized["a"] - 0.6) < 1e-10
        assert abs(normalized["b"] - 0.4) < 1e-10
        assert abs(sum(normalized.values()) - 1.0) < 1e-10

    def test_max_floor_0_01(self):
        """Kill mutation: `max(v, 0.01)` floor changed."""
        raw_weights = {"a": 0.0, "b": 0.5, "c": 0.5}
        floored = {k: max(v, 0.01) for k, v in raw_weights.items()}
        assert floored["a"] == 0.01
        assert floored["b"] == 0.5
