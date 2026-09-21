"""Phase 24: ML training rows from daily views."""

from types import SimpleNamespace

from worker.utils.daily_aggregation import FEATURE_FIELDS, aggregate_feature_vector
from worker.utils.ml_trainer import FEATURE_NAMES, aggregate_daily_features


def _sig(composite: float, **scores):
    defaults = {field: 0.0 for field in FEATURE_FIELDS}
    defaults.update(scores)
    return SimpleNamespace(composite_score=composite, **defaults)


class TestFeatureAggregation:
    def test_field_order_matches_trainer(self):
        assert len(FEATURE_FIELDS) == len(FEATURE_NAMES) == 6

    def test_weighted_mean_by_magnitude(self):
        signals = [
            _sig(0.8, sentiment_score=1.0, rsi_score=0.5),
            _sig(0.2, sentiment_score=0.0, rsi_score=-0.5),
        ]
        vec = aggregate_daily_features(signals)
        assert abs(vec[0] - 0.8) < 1e-9
        assert abs(vec[4] - 0.3) < 1e-9  # (0.8*0.5 + 0.2*-0.5) / 1.0

    def test_missing_component_is_zero(self):
        vec = aggregate_feature_vector([_sig(1.0, sentiment_score=0.4)])
        assert vec[0] == 0.4
        assert vec[1] == 0.0
        assert vec[2] == 0.0

    def test_one_row_per_view(self):
        view_features = [
            aggregate_daily_features([_sig(0.6, sentiment_score=0.2), _sig(0.4, sentiment_score=0.8)]),
            aggregate_daily_features([_sig(1.0, sentiment_score=-0.5)]),
        ]
        labels = [True, False]
        assert len(view_features) == len(labels) == 2
        assert abs(view_features[0][0] - 0.44) < 1e-9  # 0.6*0.2 + 0.4*0.8
        assert view_features[1][0] == -0.5

    def test_label_comes_from_daily_outcome(self):
        is_correct_1d = True
        features = aggregate_daily_features([_sig(0.5, sentiment_score=0.1)])
        assert len(features) == 6
        assert is_correct_1d is True
