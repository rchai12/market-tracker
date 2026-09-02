"""Shared composite-score formula used by live signal generation and backtests.

Keeping the combiner, weights, regime multiplier, and classification in one
module prevents the live pipeline and the backtester from drifting apart.
"""

from app.config import settings

# ── Base weights (4 predictive components; RSI and trend are regime-only) ──
WEIGHT_SENTIMENT_MOMENTUM = 0.40
WEIGHT_SENTIMENT_VOLUME = 0.25
WEIGHT_PRICE_MOMENTUM = 0.20
WEIGHT_VOLUME_ANOMALY = 0.15

# With options only (8% added; scale other 4 down proportionally)
WEIGHT_SENTIMENT_MOMENTUM_OPT = 0.37
WEIGHT_SENTIMENT_VOLUME_OPT = 0.23
WEIGHT_PRICE_MOMENTUM_OPT = 0.18
WEIGHT_VOLUME_ANOMALY_OPT = 0.14
WEIGHT_OPTIONS = 0.08

# With earnings only (10% added; scale other 4 down proportionally)
WEIGHT_SENTIMENT_MOMENTUM_EARN = 0.36
WEIGHT_SENTIMENT_VOLUME_EARN = 0.22
WEIGHT_PRICE_MOMENTUM_EARN = 0.18
WEIGHT_VOLUME_ANOMALY_EARN = 0.14
WEIGHT_EARNINGS = 0.10

# With both earnings (10%) + options (8%)
WEIGHT_SENTIMENT_MOMENTUM_BOTH = 0.33
WEIGHT_SENTIMENT_VOLUME_BOTH = 0.21
WEIGHT_PRICE_MOMENTUM_BOTH = 0.16
WEIGHT_VOLUME_ANOMALY_BOTH = 0.12

# ── Thresholds ──
STRONG_THRESHOLD = 0.6
MODERATE_THRESHOLD = 0.35
NEUTRAL_DEADZONE = 0.01

PREDICTIVE_KEYS = (
    "sentiment_momentum",
    "sentiment_volume",
    "price_momentum",
    "volume_anomaly",
    "earnings",
    "options",
)


def apply_regime_multiplier(
    composite: float,
    rsi_score: float | None,
    trend_score: float | None,
) -> tuple[float, str]:
    """Apply a regime-based confidence multiplier to the composite score.

    RSI and trend are not additive components — they provide context about
    market conditions and adjust how much we trust the signal.

    RSI score is tanh-scaled: positive → oversold, negative → overbought.
    Threshold |0.4| ≈ raw RSI of 35/65 (moderately extended).

    Trend score > 0.3 indicates a meaningful uptrend (SMA20 > SMA50 + positive MACD).
    Trend score < -0.3 indicates a meaningful downtrend.

    Priority order:
    1. RSI extreme (|rsi_score| > 0.4): dampen 15% regardless of trend.
    2. Strong trend confirming signal: boost 15%.
    3. Strong trend opposing signal: dampen 15%.
    4. Sideways / neutral: no change.

    Returns (adjusted_composite, regime_label).
    regime_label: "overbought" | "oversold" | "trending_up" | "trending_down" | "sideways"
    """
    rsi_val = rsi_score if rsi_score is not None else 0.0
    trend_val = trend_score if trend_score is not None else 0.0

    if abs(rsi_val) > 0.4:
        regime = "overbought" if rsi_val < 0 else "oversold"
        return composite * 0.85, regime

    if abs(trend_val) > 0.3:
        composite_bullish = composite > 0
        trend_bullish = trend_val > 0
        regime = "trending_up" if trend_bullish else "trending_down"
        if composite_bullish == trend_bullish:
            return composite * 1.15, regime
        return composite * 0.85, regime

    return composite, "sideways"


def default_weights(has_options: bool | None = None, has_earnings: bool = False) -> dict:
    """Return default weights for the 4-component base formula.

    RSI and trend are 0.0 — they are used only for regime classification.
    Earnings (10%) is included only when a reported surprise is in the 48h window.
    """
    if has_options is None:
        has_options = settings.options_flow_enabled
    if has_options and has_earnings:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_BOTH,
            "sentiment_volume": WEIGHT_SENTIMENT_VOLUME_BOTH,
            "price_momentum": WEIGHT_PRICE_MOMENTUM_BOTH,
            "volume_anomaly": WEIGHT_VOLUME_ANOMALY_BOTH,
            "rsi": 0.0,
            "trend": 0.0,
            "earnings": WEIGHT_EARNINGS,
            "options": WEIGHT_OPTIONS,
            "source": "default",
        }
    if has_options:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_OPT,
            "sentiment_volume": WEIGHT_SENTIMENT_VOLUME_OPT,
            "price_momentum": WEIGHT_PRICE_MOMENTUM_OPT,
            "volume_anomaly": WEIGHT_VOLUME_ANOMALY_OPT,
            "rsi": 0.0,
            "trend": 0.0,
            "earnings": 0.0,
            "options": WEIGHT_OPTIONS,
            "source": "default",
        }
    if has_earnings:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_EARN,
            "sentiment_volume": WEIGHT_SENTIMENT_VOLUME_EARN,
            "price_momentum": WEIGHT_PRICE_MOMENTUM_EARN,
            "volume_anomaly": WEIGHT_VOLUME_ANOMALY_EARN,
            "rsi": 0.0,
            "trend": 0.0,
            "earnings": WEIGHT_EARNINGS,
            "options": 0.0,
            "source": "default",
        }
    return {
        "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM,
        "sentiment_volume": WEIGHT_SENTIMENT_VOLUME,
        "price_momentum": WEIGHT_PRICE_MOMENTUM,
        "volume_anomaly": WEIGHT_VOLUME_ANOMALY,
        "rsi": 0.0,
        "trend": 0.0,
        "earnings": 0.0,
        "options": 0.0,
        "source": "default",
    }


def apply_component_gates(weights: dict, has_earnings: bool, has_options: bool) -> dict:
    """Zero inactive gated components and renormalize predictive weights to 1.0.

    Copies the input so cached adaptive-weight maps are never mutated in place.
    RSI/trend stay 0.0 (regime context only).
    """
    w = dict(weights)
    if not has_earnings:
        w["earnings"] = 0.0
    if not has_options:
        w["options"] = 0.0
    w["rsi"] = 0.0
    w["trend"] = 0.0

    total = sum(float(w.get(k, 0.0) or 0.0) for k in PREDICTIVE_KEYS)
    if total > 0:
        for k in PREDICTIVE_KEYS:
            w[k] = float(w.get(k, 0.0) or 0.0) / total
    return w


def resolve_weights(
    weights_map: dict | None,
    sector_id: int | None,
    has_earnings: bool = False,
    has_options: bool | None = None,
) -> dict:
    """Look up adaptive weights: sector-specific -> global -> defaults, then gate."""
    if has_options is None:
        has_options = settings.options_flow_enabled
    if weights_map:
        if sector_id is not None and sector_id in weights_map:
            return apply_component_gates(weights_map[sector_id], has_earnings, has_options)
        if None in weights_map:
            return apply_component_gates(weights_map[None], has_earnings, has_options)
    return default_weights(has_options=has_options, has_earnings=has_earnings)


def classify_direction(composite: float) -> str:
    if composite > NEUTRAL_DEADZONE:
        return "bullish"
    if composite < -NEUTRAL_DEADZONE:
        return "bearish"
    return "neutral"


def classify_strength(composite: float) -> str:
    abs_score = abs(composite)
    if abs_score > STRONG_THRESHOLD:
        return "strong"
    if abs_score > MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


def combine_component_scores(
    *,
    sentiment_momentum: float | None,
    sentiment_volume: float | None,
    price_momentum: float | None,
    volume_anomaly: float | None,
    rsi_score: float | None,
    trend_score: float | None,
    options_score: float | None = None,
    earnings_score: float | None = None,
    weights: dict | None = None,
    has_options: bool | None = None,
    article_count: int = 0,
) -> dict | None:
    """Combine component scores into a regime-adjusted composite.

    Missing sentiment/price/volume/RSI/trend values are treated as 0.0 in the
    math (and in the returned dict, matching historical persistence).
    Earnings and options preserve None vs 0.0: None means the gate is inactive,
    0.0 means the component was active and scored exactly zero.
    """
    has_sentiment = sentiment_momentum is not None
    has_market = (
        price_momentum is not None
        or volume_anomaly is not None
        or rsi_score is not None
        or trend_score is not None
    )
    if not has_sentiment and not has_market:
        return None

    has_earnings = earnings_score is not None
    if has_options is None:
        has_options = settings.options_flow_enabled

    if weights is None:
        w = default_weights(has_options=has_options, has_earnings=has_earnings)
    else:
        w = apply_component_gates(weights, has_earnings, has_options)

    sm = sentiment_momentum if sentiment_momentum is not None else 0.0
    sv = sentiment_volume if sentiment_volume is not None else 0.0
    pm = price_momentum if price_momentum is not None else 0.0
    va = volume_anomaly if volume_anomaly is not None else 0.0
    rsi_val = rsi_score if rsi_score is not None else 0.0
    trend_val = trend_score if trend_score is not None else 0.0
    opts_val = options_score if options_score is not None else 0.0
    earn_val = earnings_score if earnings_score is not None else 0.0

    raw_composite = (
        w["sentiment_momentum"] * sm
        + w["sentiment_volume"] * sv
        + w["price_momentum"] * pm
        + w["volume_anomaly"] * va
        + float(w.get("options", 0.0)) * opts_val
        + float(w.get("earnings", 0.0)) * earn_val
    )
    composite, market_regime = apply_regime_multiplier(raw_composite, rsi_val, trend_val)

    return {
        "composite": composite,
        "sentiment_momentum": sm,
        "sentiment_volume": sv,
        "price_momentum": pm,
        "volume_anomaly": va,
        "rsi_score": rsi_val,
        "trend_score": trend_val,
        "options_score": options_score,
        "earnings_score": earnings_score,
        "market_regime": market_regime,
        "article_count": article_count,
        "weights_source": w.get("source", "default"),
    }
