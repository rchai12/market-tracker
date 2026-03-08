"""Tests for the LightGBM ML trainer module."""

import json
from pathlib import Path

import numpy as np
import pytest

from worker.utils.ml_trainer import (
    FEATURE_NAMES,
    PredictionResult,
    TrainingResult,
    _accuracy,
    _f1,
    clear_cache,
    load_model,
    predict,
    train_model,
)


# ── Helper: generate synthetic training data ──


def _make_data(n: int, seed: int = 42) -> tuple[list[list[float]], list[bool]]:
    """Generate synthetic features and labels for testing.

    Features are 6 component scores in [-1, 1].
    Labels are correlated with feature sum (positive sum → more likely correct).
    """
    rng = np.random.RandomState(seed)
    features = (rng.rand(n, 6) * 2 - 1).tolist()  # [-1, 1]
    labels = []
    for row in features:
        # Signal is "correct" if sum of components > 0 (with some noise)
        prob_correct = 1.0 / (1.0 + np.exp(-sum(row)))
        labels.append(bool(rng.rand() < prob_correct))
    return features, labels


# ── Metric helpers ──


class TestAccuracy:
    def test_perfect(self):
        assert _accuracy([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0

    def test_zero(self):
        assert _accuracy([1, 1, 1], [0, 0, 0]) == 0.0

    def test_partial(self):
        assert _accuracy([1, 0, 1, 0], [1, 1, 0, 0]) == 0.5

    def test_empty(self):
        assert _accuracy([], []) == 0.0


class TestF1:
    def test_perfect(self):
        assert _f1([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0

    def test_no_positives_predicted(self):
        assert _f1([1, 1, 1], [0, 0, 0]) == 0.0

    def test_no_positives_in_truth(self):
        assert _f1([0, 0, 0], [1, 1, 1]) == 0.0

    def test_partial(self):
        # TP=1, FP=1, FN=1 → P=0.5, R=0.5, F1=0.5
        assert _f1([1, 1, 0], [1, 0, 1]) == 0.5


# ── Training ──


class TestTrainModel:
    def test_trains_with_sufficient_data(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "test_sector", 1)
        assert result is not None
        assert isinstance(result, TrainingResult)
        assert result.training_samples == 200
        assert Path(result.model_path).exists()

    def test_returns_none_with_insufficient_data(self, tmp_path):
        features, labels = _make_data(10)
        result = train_model(features, labels, str(tmp_path), "test_sector", 1)
        assert result is None

    def test_model_file_created(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "test_sector", 1)
        assert result is not None
        assert Path(result.model_path).exists()
        assert result.model_path.endswith(".txt")

    def test_validation_metrics_range(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "test_sector", 1)
        assert result is not None
        assert 0 <= result.validation_accuracy <= 100
        assert 0 <= result.validation_f1 <= 1.0

    def test_feature_importances_all_features(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "test_sector", 1)
        assert result is not None
        assert set(result.feature_importances.keys()) == set(FEATURE_NAMES)
        assert all(v >= 0 for v in result.feature_importances.values())

    def test_training_config_saved(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "test_sector", 1)
        assert result is not None
        assert "objective" in result.training_config
        assert result.training_config["objective"] == "binary"

    def test_sector_name_slug(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "Communication Services", 1)
        assert result is not None
        assert "communication_services" in result.model_path

    def test_version_in_filename(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "test", 5)
        assert result is not None
        assert "model_v5.txt" in result.model_path

    def test_insufficient_after_split(self, tmp_path):
        """Too few samples for valid train/val split."""
        features, labels = _make_data(15)
        result = train_model(features, labels, str(tmp_path), "test", 1)
        assert result is None


# ── Prediction ──


class TestPredict:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Train a model and provide its path for prediction tests."""
        clear_cache()
        features, labels = _make_data(300)
        result = train_model(features, labels, str(tmp_path), "predict_test", 1)
        assert result is not None
        self.model_path = result.model_path

    def test_prediction_result_structure(self):
        features = [0.5, 0.3, 0.2, 0.1, 0.4, 0.3]
        result = predict(self.model_path, features, "bullish")
        assert result is not None
        assert isinstance(result, PredictionResult)
        assert hasattr(result, "ml_score")
        assert hasattr(result, "ml_direction")
        assert hasattr(result, "ml_confidence")

    def test_score_range(self):
        features = [0.5, 0.3, 0.2, 0.1, 0.4, 0.3]
        result = predict(self.model_path, features, "bullish")
        assert result is not None
        assert -1.0 <= result.ml_score <= 1.0
        assert 0.0 <= result.ml_confidence <= 1.0

    def test_direction_valid_values(self):
        features = [0.5, 0.3, 0.2, 0.1, 0.4, 0.3]
        result = predict(self.model_path, features, "bullish")
        assert result is not None
        assert result.ml_direction in ("bullish", "bearish", "neutral")

    def test_returns_none_for_missing_model(self):
        result = predict("/nonexistent/model.txt", [0.0] * 6, "bullish")
        assert result is None

    def test_neutral_composite_direction(self):
        features = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        result = predict(self.model_path, features, "neutral")
        assert result is not None
        # With neutral composite direction, ml_direction should be neutral or low-confidence
        assert result.ml_direction in ("bullish", "bearish", "neutral")


# ── Model cache ──


class TestModelCache:
    def test_cache_hit(self, tmp_path):
        clear_cache()
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "cache_test", 1)
        assert result is not None

        # First load (already cached from training)
        model1 = load_model(result.model_path)
        # Second load (cache hit)
        model2 = load_model(result.model_path)
        assert model1 is model2

    def test_clear_cache(self, tmp_path):
        features, labels = _make_data(200)
        result = train_model(features, labels, str(tmp_path), "cache_clear", 1)
        assert result is not None

        clear_cache()
        # After clearing, load should re-read from disk
        model = load_model(result.model_path)
        assert model is not None

    def test_missing_file_returns_none(self):
        clear_cache()
        model = load_model("/nonexistent/path.txt")
        assert model is None
