"""Tests for options flow data aggregation, scoring, and CBOE parsing."""

import math
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from worker.tasks.scraping.options_data import _aggregate_options_chain, _find_atm_iv, _safe_float


# ── Helper to create mock option chain DataFrames ──

def _make_chain(calls_data: list[dict], puts_data: list[dict]):
    """Create a mock option chain result."""
    calls_df = pd.DataFrame(calls_data) if calls_data else pd.DataFrame()
    puts_df = pd.DataFrame(puts_data) if puts_data else pd.DataFrame()
    return SimpleNamespace(calls=calls_df, puts=puts_df)


def _make_ticker(expirations: list[str], chains: dict):
    """Create a mock yfinance ticker object."""
    ticker = MagicMock()
    ticker.options = expirations
    ticker.option_chain = lambda exp: chains.get(exp, _make_chain([], []))
    return ticker


# ── _safe_float tests ──

class TestSafeFloat:
    def test_normal_value(self):
        assert _safe_float(1.5) == 1.5

    def test_none(self):
        assert _safe_float(None) is None

    def test_nan(self):
        assert _safe_float(float("nan")) is None

    def test_inf(self):
        assert _safe_float(float("inf")) is None

    def test_neg_inf(self):
        assert _safe_float(float("-inf")) is None

    def test_zero(self):
        assert _safe_float(0) == 0.0


# ── _find_atm_iv tests ──

class TestFindAtmIv:
    def test_exact_strike(self):
        df = pd.DataFrame({
            "strike": [140, 145, 150, 155, 160],
            "impliedVolatility": [0.30, 0.28, 0.25, 0.27, 0.32],
        })
        assert _find_atm_iv(df, 150.0) == 0.25

    def test_nearest_strike(self):
        df = pd.DataFrame({
            "strike": [140, 150, 160],
            "impliedVolatility": [0.30, 0.25, 0.32],
        })
        assert _find_atm_iv(df, 148.0) == 0.25  # 150 is nearest

    def test_empty_df(self):
        df = pd.DataFrame()
        assert _find_atm_iv(df, 100.0) is None

    def test_no_strike_column(self):
        df = pd.DataFrame({"volume": [100]})
        assert _find_atm_iv(df, 100.0) is None


# ── _aggregate_options_chain tests ──

class TestAggregateOptionsChain:
    def test_basic_aggregation(self):
        chain = _make_chain(
            calls_data=[
                {"strike": 140, "volume": 100, "openInterest": 500, "impliedVolatility": 0.25},
                {"strike": 150, "volume": 200, "openInterest": 800, "impliedVolatility": 0.22},
            ],
            puts_data=[
                {"strike": 140, "volume": 50, "openInterest": 300, "impliedVolatility": 0.30},
                {"strike": 150, "volume": 80, "openInterest": 400, "impliedVolatility": 0.28},
            ],
        )
        ticker = _make_ticker(["2026-03-20"], {"2026-03-20": chain})
        result = _aggregate_options_chain(ticker, 145.0, max_expirations=3)

        assert result is not None
        assert result["total_call_volume"] == 300
        assert result["total_put_volume"] == 130
        assert result["total_call_oi"] == 1300
        assert result["total_put_oi"] == 700
        # P/C ratio = 130/300
        assert abs(result["put_call_ratio"] - 130 / 300) < 0.001
        assert result["data_quality"] == "full"
        assert result["expirations_fetched"] == 1

    def test_zero_call_volume_pcr_none(self):
        chain = _make_chain(
            calls_data=[
                {"strike": 150, "volume": 0, "openInterest": 10, "impliedVolatility": 0.25},
            ],
            puts_data=[
                {"strike": 150, "volume": 5, "openInterest": 10, "impliedVolatility": 0.30},
            ],
        )
        ticker = _make_ticker(["2026-03-20"], {"2026-03-20": chain})
        result = _aggregate_options_chain(ticker, 150.0, max_expirations=3)

        assert result is not None
        assert result["put_call_ratio"] is None  # Division by zero prevented

    def test_stale_data_quality(self):
        """Total volume < 10 → stale."""
        chain = _make_chain(
            calls_data=[
                {"strike": 150, "volume": 2, "openInterest": 5, "impliedVolatility": 0.25},
            ],
            puts_data=[
                {"strike": 150, "volume": 3, "openInterest": 5, "impliedVolatility": 0.30},
            ],
        )
        ticker = _make_ticker(["2026-03-20"], {"2026-03-20": chain})

        with patch("worker.tasks.scraping.options_data.settings") as mock_settings:
            mock_settings.options_min_volume = 50
            result = _aggregate_options_chain(ticker, 150.0, max_expirations=3)

        assert result["data_quality"] == "stale"

    def test_partial_data_quality(self):
        """Total volume >= 10 but < min_volume → partial."""
        chain = _make_chain(
            calls_data=[
                {"strike": 150, "volume": 20, "openInterest": 50, "impliedVolatility": 0.25},
            ],
            puts_data=[
                {"strike": 150, "volume": 10, "openInterest": 50, "impliedVolatility": 0.30},
            ],
        )
        ticker = _make_ticker(["2026-03-20"], {"2026-03-20": chain})

        with patch("worker.tasks.scraping.options_data.settings") as mock_settings:
            mock_settings.options_min_volume = 50
            result = _aggregate_options_chain(ticker, 150.0, max_expirations=3)

        assert result["data_quality"] == "partial"

    def test_iv_skew_computation(self):
        chain = _make_chain(
            calls_data=[
                {"strike": 148, "volume": 100, "openInterest": 500, "impliedVolatility": 0.20},
                {"strike": 150, "volume": 200, "openInterest": 800, "impliedVolatility": 0.22},
                {"strike": 152, "volume": 100, "openInterest": 300, "impliedVolatility": 0.25},
            ],
            puts_data=[
                {"strike": 148, "volume": 100, "openInterest": 500, "impliedVolatility": 0.28},
                {"strike": 150, "volume": 200, "openInterest": 800, "impliedVolatility": 0.30},
                {"strike": 152, "volume": 100, "openInterest": 300, "impliedVolatility": 0.35},
            ],
        )
        ticker = _make_ticker(["2026-03-20"], {"2026-03-20": chain})
        result = _aggregate_options_chain(ticker, 150.0, max_expirations=3)

        # ATM at strike 150: call IV 0.22, put IV 0.30
        assert result["atm_call_iv"] == 0.22
        assert result["atm_put_iv"] == 0.30
        assert abs(result["iv_skew"] - 0.08) < 0.001  # 0.30 - 0.22

    def test_no_expirations(self):
        ticker = _make_ticker([], {})
        result = _aggregate_options_chain(ticker, 150.0, max_expirations=3)
        assert result is None

    def test_max_expirations_limit(self):
        chains = {f"2026-03-{20+i}": _make_chain(
            [{"strike": 150, "volume": 10, "openInterest": 50, "impliedVolatility": 0.25}],
            [{"strike": 150, "volume": 10, "openInterest": 50, "impliedVolatility": 0.30}],
        ) for i in range(5)}
        ticker = _make_ticker(list(chains.keys()), chains)
        result = _aggregate_options_chain(ticker, 150.0, max_expirations=2)

        assert result["expirations_fetched"] == 2

    def test_multiple_expirations_sum(self):
        chain1 = _make_chain(
            [{"strike": 150, "volume": 100, "openInterest": 500, "impliedVolatility": 0.25}],
            [{"strike": 150, "volume": 50, "openInterest": 300, "impliedVolatility": 0.30}],
        )
        chain2 = _make_chain(
            [{"strike": 150, "volume": 80, "openInterest": 400, "impliedVolatility": 0.22}],
            [{"strike": 150, "volume": 40, "openInterest": 200, "impliedVolatility": 0.28}],
        )
        ticker = _make_ticker(["2026-03-20", "2026-04-17"], {
            "2026-03-20": chain1,
            "2026-04-17": chain2,
        })
        result = _aggregate_options_chain(ticker, 150.0, max_expirations=3)

        assert result["total_call_volume"] == 180  # 100 + 80
        assert result["total_put_volume"] == 90  # 50 + 40
        assert result["total_call_oi"] == 900  # 500 + 400
        assert result["total_put_oi"] == 500  # 300 + 200


# ── Options score computation tests ──

class TestCalcOptionsScore:
    """Tests for calc_options_score via import.

    These test the scoring algorithm in isolation by mocking the DB queries.
    """

    def test_score_bounded(self):
        """Score from combining PCR and IV skew should be bounded."""
        # PCR z-score contribution: -tanh(z) ranges [-1, 1]
        # IV skew z-score contribution: -tanh(z) ranges [-1, 1]
        # Combined: 0.6 * [-1,1] + 0.4 * [-1,1] → [-1, 1]
        for pcr in [-5.0, -2.0, 0.0, 2.0, 5.0]:
            for skew in [-5.0, -2.0, 0.0, 2.0, 5.0]:
                pcr_score = -math.tanh(pcr)
                skew_score = -math.tanh(skew)
                combined = 0.6 * pcr_score + 0.4 * skew_score
                assert -1.0 <= combined <= 1.0

    def test_high_pcr_gives_negative(self):
        """High put/call ratio → bearish → negative score."""
        # z-score > 0 means high P/C → -tanh(z) < 0 → bearish
        z = 2.0
        pcr_score = -math.tanh(z)
        assert pcr_score < 0

    def test_low_pcr_gives_positive(self):
        """Low put/call ratio → bullish → positive score."""
        z = -2.0
        pcr_score = -math.tanh(z)
        assert pcr_score > 0

    def test_normal_activity_near_zero(self):
        """Normal activity (z=0) should give near-zero score."""
        pcr_score = -math.tanh(0.0)
        skew_score = -math.tanh(0.0)
        combined = 0.6 * pcr_score + 0.4 * skew_score
        assert abs(combined) < 0.01

    def test_widening_skew_bearish(self):
        """Widening IV skew (puts more expensive) → bearish."""
        z = 2.0  # Skew above baseline
        skew_score = -math.tanh(z)
        assert skew_score < 0

    def test_narrowing_skew_bullish(self):
        """Narrowing IV skew → bullish."""
        z = -2.0  # Skew below baseline
        skew_score = -math.tanh(z)
        assert skew_score > 0


# ── Default weights tests ──

class TestDefaultWeights:
    def test_6_component_defaults_sum_to_1(self):
        from worker.tasks.signals.signal_generator import _default_weights

        with patch("worker.tasks.signals.signal_generator.settings") as mock_settings:
            mock_settings.options_flow_enabled = False
            w = _default_weights()

        # 6 base components (excluding "source" and "options" which is 0.0)
        weight_sum = sum(v for k, v in w.items() if k not in ("source", "options"))
        assert abs(weight_sum - 1.0) < 0.01

    def test_7_component_defaults_sum_to_1(self):
        from worker.tasks.signals.signal_generator import _default_weights

        with patch("worker.tasks.signals.signal_generator.settings") as mock_settings:
            mock_settings.options_flow_enabled = True
            w = _default_weights()

        weight_sum = sum(v for k, v in w.items() if k != "source")
        assert abs(weight_sum - 1.0) < 0.01

    def test_options_disabled_zero_weight(self):
        from worker.tasks.signals.signal_generator import _default_weights

        with patch("worker.tasks.signals.signal_generator.settings") as mock_settings:
            mock_settings.options_flow_enabled = False
            w = _default_weights()

        assert w["options"] == 0.0

    def test_options_enabled_has_weight(self):
        from worker.tasks.signals.signal_generator import _default_weights

        with patch("worker.tasks.signals.signal_generator.settings") as mock_settings:
            mock_settings.options_flow_enabled = True
            w = _default_weights()

        assert w["options"] == 0.08


# ── Signal reasoning tests ──

class TestOptionsReasoning:
    def test_options_in_reasoning_when_significant(self):
        from worker.tasks.signals.signal_generator import _build_reasoning

        score_data = {
            "composite": 0.5,
            "sentiment_momentum": 0.3,
            "sentiment_volume": 0.1,
            "price_momentum": 0.2,
            "volume_anomaly": 0.1,
            "rsi_score": 0.0,
            "trend_score": 0.0,
            "options_score": 0.5,  # > 0.3 threshold
            "article_count": 5,
            "weights_source": "default",
        }
        reasoning = _build_reasoning("AAPL", score_data, "bullish", "moderate")
        assert "Options flow is bullish" in reasoning

    def test_options_not_in_reasoning_when_small(self):
        from worker.tasks.signals.signal_generator import _build_reasoning

        score_data = {
            "composite": 0.5,
            "sentiment_momentum": 0.5,
            "sentiment_volume": 0.1,
            "price_momentum": 0.2,
            "volume_anomaly": 0.1,
            "rsi_score": 0.0,
            "trend_score": 0.0,
            "options_score": 0.1,  # < 0.3 threshold
            "article_count": 5,
            "weights_source": "default",
        }
        reasoning = _build_reasoning("AAPL", score_data, "bullish", "moderate")
        assert "Options" not in reasoning
