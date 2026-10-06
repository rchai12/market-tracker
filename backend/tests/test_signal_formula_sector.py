"""Phase 25b: sector sentiment gate in the shared formula."""

from worker.utils.signal_formula import (
    WEIGHT_SECTOR_SENTIMENT,
    WEIGHT_SENTIMENT_MOMENTUM,
    apply_component_gates,
    combine_component_scores,
    default_weights,
    methodology_defaults,
)


def _numeric_sum(weights: dict) -> float:
    return sum(v for k, v in weights.items() if k != "source")


class TestSectorSentimentFormula:
    def test_weight_is_0_05(self):
        assert WEIGHT_SECTOR_SENTIMENT == 0.05

    def test_has_sector_sentiment_scales_base_weights(self):
        w = default_weights(has_options=False, has_earnings=False, has_sector_sentiment=True)
        assert abs(w["sector_sentiment"] - 0.05) < 1e-9
        assert abs(w["sentiment_momentum"] - WEIGHT_SENTIMENT_MOMENTUM * 0.95) < 1e-9
        assert abs(_numeric_sum(w) - 1.0) < 1e-9

    def test_inactive_sector_stays_zero(self):
        w = default_weights(has_options=False, has_earnings=False, has_sector_sentiment=False)
        assert w["sector_sentiment"] == 0.0
        assert abs(_numeric_sum(w) - 1.0) < 1e-9

    def test_apply_gates_injects_default_when_active(self):
        w0 = default_weights(has_options=False, has_earnings=False)
        w = apply_component_gates(w0, has_earnings=False, has_options=False, has_sector_sentiment=True)
        expected = WEIGHT_SECTOR_SENTIMENT / (1.0 + WEIGHT_SECTOR_SENTIMENT)
        assert abs(w["sector_sentiment"] - expected) < 1e-9
        assert abs(_numeric_sum(w) - 1.0) < 1e-9

    def test_score_enters_composite_when_present(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            sector_sentiment_score=0.4,
            has_options=False,
        )
        assert result is not None
        assert result["sector_sentiment_score"] == 0.4
        scale = 0.95
        raw = 0.40 * scale * 0.5 + 0.25 * scale * 0.2 + 0.20 * scale * 0.3 + 0.15 * scale * 0.1 + 0.05 * 0.4
        assert abs(result["composite"] - raw) < 1e-9

    def test_none_score_leaves_base_formula(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            sector_sentiment_score=None,
            has_options=False,
        )
        assert result is not None
        assert result["sector_sentiment_score"] is None
        raw = 0.40 * 0.5 + 0.25 * 0.2 + 0.20 * 0.3 + 0.15 * 0.1
        assert abs(result["composite"] - raw) < 1e-9

    def test_zero_score_is_active_gate(self):
        result = combine_component_scores(
            sentiment_momentum=0.5,
            sentiment_volume=0.2,
            price_momentum=0.3,
            volume_anomaly=0.1,
            rsi_score=None,
            trend_score=None,
            sector_sentiment_score=0.0,
            has_options=False,
        )
        assert result is not None
        assert result["sector_sentiment_score"] == 0.0
        scale = 0.95
        raw = 0.40 * scale * 0.5 + 0.25 * scale * 0.2 + 0.20 * scale * 0.3 + 0.15 * scale * 0.1
        assert abs(result["composite"] - raw) < 1e-9

    def test_methodology_defaults_include_sector(self):
        d = methodology_defaults()
        assert d["sector_sentiment"] == WEIGHT_SECTOR_SENTIMENT
