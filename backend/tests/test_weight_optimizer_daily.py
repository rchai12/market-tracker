"""Phase 24: proportional credit from daily-view outcomes."""

from types import SimpleNamespace
from unittest.mock import patch

from worker.tasks.signals.weight_optimizer import _weights_from_rows, learning_pct_for_outcome
from worker.utils.daily_aggregation import expand_view_credits, majority_regime


def _sig(composite, direction="bullish", regime="sideways", **scores):
    defaults = dict(
        sentiment_score=0.5,
        price_score=0.2,
        volume_score=0.1,
        options_score=None,
        earnings_score=None,
        analyst_score=None,
        insider_score=None,
        market_regime=regime,
    )
    defaults.update(scores)
    return SimpleNamespace(composite_score=composite, direction=direction, **defaults)


class TestProportionalCredit:
    def test_larger_contributor_gets_larger_vote(self):
        strong = _sig(0.7, sentiment_score=0.9, price_score=-0.9)
        weak = _sig(0.3, sentiment_score=-0.9, price_score=0.9)
        rows = expand_view_credits([strong, weak], price_change_pct=0.05, is_correct=True)
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            settings.feedback_min_samples = 1
            settings.options_flow_enabled = False
            settings.insider_flow_enabled = False
            settings.feedback_weight_min = 0.05
            settings.feedback_weight_max = 0.60
            result = _weights_from_rows(rows, sample_count=1, correct_count=1)
        assert result is not None
        assert result["sample_count"] == 1
        assert result["sentiment_momentum"] > result["price_momentum"]

    def test_sample_count_is_views_not_exploded_signals(self):
        view_a = expand_view_credits([_sig(0.6), _sig(0.4)], price_change_pct=0.03, is_correct=True)
        view_b = expand_view_credits([_sig(0.5)], price_change_pct=-0.02, is_correct=False)
        rows = view_a + view_b
        assert len(rows) == 3
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            settings.feedback_min_samples = 2
            settings.options_flow_enabled = False
            settings.insider_flow_enabled = False
            settings.feedback_weight_min = 0.05
            settings.feedback_weight_max = 0.60
            result = _weights_from_rows(rows, sample_count=2, correct_count=1)
        assert result is not None
        assert result["sample_count"] == 2
        assert abs(result["accuracy_pct"] - 50.0) < 1e-9

    def test_return_weighting_still_applies(self):
        big = expand_view_credits(
            [_sig(1.0, sentiment_score=0.8, price_score=-0.8)],
            price_change_pct=0.05,
            is_correct=True,
        )
        small = expand_view_credits(
            [_sig(1.0, sentiment_score=-0.8, price_score=0.8)],
            price_change_pct=0.001,
            is_correct=True,
        )
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            settings.feedback_min_samples = 2
            settings.options_flow_enabled = False
            settings.insider_flow_enabled = False
            settings.feedback_weight_min = 0.05
            settings.feedback_weight_max = 0.60
            result = _weights_from_rows(big + small, sample_count=2, correct_count=2)
        assert result is not None
        assert result["sentiment_momentum"] > result["price_momentum"]


class TestMajorityRegime:
    def test_majority_label(self):
        signals = [
            _sig(0.5, regime="oversold"),
            _sig(0.4, regime="oversold"),
            _sig(0.3, regime="sideways"),
        ]
        assert majority_regime(signals) == "oversold"


def _optimizer_settings(settings) -> None:
    settings.feedback_min_samples = 1
    settings.options_flow_enabled = False
    settings.insider_flow_enabled = False
    settings.feedback_weight_min = 0.05
    settings.feedback_weight_max = 0.60


class TestLearningPctForOutcome:
    def test_prefers_excess_return(self):
        outcome = SimpleNamespace(price_change_pct=0.01, excess_return_pct=-0.01)
        assert learning_pct_for_outcome(outcome) == -0.01

    def test_market_etf_falls_back_to_absolute_return(self):
        outcome = SimpleNamespace(price_change_pct=0.02, excess_return_pct=None)
        assert learning_pct_for_outcome(outcome) == 0.02

    def test_zero_excess_is_used_not_fallback(self):
        outcome = SimpleNamespace(price_change_pct=0.02, excess_return_pct=0.0)
        assert learning_pct_for_outcome(outcome) == 0.0


class TestExcessReturnCredits:
    def test_optimizer_uses_excess_return_direction_for_credit(self):
        outcome = SimpleNamespace(price_change_pct=0.01, excess_return_pct=-0.01, is_correct=False)
        sig = _sig(0.8, sentiment_score=0.9, price_score=-0.9, volume_score=0.9)
        rows = expand_view_credits(
            [sig],
            learning_pct_for_outcome(outcome),
            bool(outcome.is_correct),
        )
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            _optimizer_settings(settings)
            result = _weights_from_rows(rows, sample_count=1, correct_count=0)
        assert result is not None
        assert result["price_momentum"] > result["sentiment_momentum"]
        assert result["price_momentum"] > result["volume_anomaly"]

    def test_sentiment_volume_agrees_with_other_components_on_direction(self):
        sig = _sig(
            0.8,
            sentiment_score=0.5,
            price_score=0.5,
            volume_score=0.5,
            sentiment_volume_score=0.5,
        )
        rows = expand_view_credits([sig], price_change_pct=0.04, is_correct=True)
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            _optimizer_settings(settings)
            result = _weights_from_rows(rows, sample_count=1, correct_count=1)
        assert result is not None
        assert abs(result["sentiment_volume"] - result["sentiment_momentum"]) < 1e-9

    def test_sentiment_volume_follows_actual_dir_when_is_correct_disagrees(self):
        sig = _sig(
            0.8,
            sentiment_score=0.5,
            price_score=0.5,
            volume_score=0.5,
            sentiment_volume_score=0.5,
        )
        rows = expand_view_credits([sig], price_change_pct=0.04, is_correct=False)
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            _optimizer_settings(settings)
            result = _weights_from_rows(rows, sample_count=1, correct_count=0)
        assert result is not None
        assert abs(result["sentiment_volume"] - result["sentiment_momentum"]) < 1e-9
