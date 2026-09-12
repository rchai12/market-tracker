"""Phase 22b: return-weighted outcomes, analyst in optimizer, regime weights."""

from types import SimpleNamespace
from unittest.mock import patch

from worker.tasks.signals.weight_optimizer import _weights_from_rows
from worker.utils.signal_formula import resolve_weights


def _row(**overrides):
    base = dict(
        sentiment_score=0.5,
        price_score=0.2,
        volume_score=0.1,
        options_score=None,
        earnings_score=None,
        analyst_score=None,
        direction="bullish",
        is_correct=True,
        price_change_pct=0.05,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _adaptive(sm: float, source: str) -> dict:
    others = (1.0 - sm) / 3
    return {
        "sentiment_momentum": sm,
        "sentiment_volume": others,
        "price_momentum": others,
        "volume_anomaly": others,
        "earnings": 0.0,
        "options": 0.0,
        "analyst": 0.0,
        "rsi": 0.0,
        "trend": 0.0,
        "source": source,
    }


class TestReturnWeightedAccuracy:
    def test_large_move_outweighs_small_move(self):
        # Sentiment correct on +5%, wrong on +0.1%. Price is the opposite.
        rows = [
            _row(sentiment_score=0.5, price_score=-0.5, price_change_pct=5.0, is_correct=True),
            _row(sentiment_score=-0.5, price_score=0.5, price_change_pct=0.1, is_correct=True),
        ]
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            settings.feedback_min_samples = 2
            settings.options_flow_enabled = False
            settings.insider_flow_enabled = False
            settings.feedback_weight_min = 0.05
            settings.feedback_weight_max = 0.60
            result = _weights_from_rows(rows)
        assert result is not None
        assert result["sentiment_momentum"] > result["price_momentum"]

    def test_below_min_samples_returns_none(self):
        rows = [_row() for _ in range(3)]
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            settings.feedback_min_samples = 50
            settings.options_flow_enabled = False
            settings.insider_flow_enabled = False
            settings.feedback_weight_min = 0.05
            settings.feedback_weight_max = 0.60
            assert _weights_from_rows(rows) is None


class TestAnalystInOptimizer:
    def test_analyst_in_result_weights(self):
        rows = [_row(analyst_score=0.4) for _ in range(3)]
        with patch("worker.tasks.signals.weight_optimizer.settings") as settings:
            settings.feedback_min_samples = 2
            settings.options_flow_enabled = False
            settings.insider_flow_enabled = False
            settings.feedback_weight_min = 0.05
            settings.feedback_weight_max = 0.60
            result = _weights_from_rows(rows)
        assert result is not None
        assert "analyst" in result
        assert result["analyst"] >= 0.05


class TestResolveWeightsRegime:
    def test_sector_regime_beats_sector(self):
        weights_map = {1: _adaptive(0.40, "sector")}
        regime_map = {(1, "oversold"): _adaptive(0.50, "regime")}
        w = resolve_weights(
            weights_map,
            sector_id=1,
            has_earnings=False,
            has_options=False,
            market_regime="oversold",
            regime_weights_map=regime_map,
        )
        assert w["source"] == "regime"
        assert abs(w["sentiment_momentum"] - 0.50) < 1e-9

    def test_global_regime_when_sector_regime_missing(self):
        weights_map = {1: _adaptive(0.40, "sector")}
        regime_map = {(None, "trending_up"): _adaptive(0.30, "regime")}
        w = resolve_weights(
            weights_map,
            sector_id=1,
            has_earnings=False,
            has_options=False,
            market_regime="trending_up",
            regime_weights_map=regime_map,
        )
        assert w["source"] == "regime"
        assert abs(w["sentiment_momentum"] - 0.30) < 1e-9

    def test_falls_back_to_sector_when_no_regime_match(self):
        weights_map = {1: _adaptive(0.40, "sector")}
        w = resolve_weights(
            weights_map,
            sector_id=1,
            has_earnings=False,
            has_options=False,
            market_regime="sideways",
            regime_weights_map={(2, "sideways"): _adaptive(0.55, "regime")},
        )
        assert w["source"] == "sector"
        assert abs(w["sentiment_momentum"] - 0.40) < 1e-9

    def test_falls_back_to_global_then_default(self):
        weights_map = {None: _adaptive(0.35, "global")}
        w = resolve_weights(
            weights_map,
            sector_id=99,
            has_earnings=False,
            has_options=False,
            market_regime="sideways",
            regime_weights_map={},
        )
        assert w["source"] == "global"
        defaulted = resolve_weights(
            {},
            sector_id=99,
            has_earnings=False,
            has_options=False,
            market_regime="sideways",
            regime_weights_map={},
        )
        assert defaulted["source"] == "default"
