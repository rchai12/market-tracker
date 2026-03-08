"""Signal component functions for the backtesting engine.

Pure functions that compute individual signal components from price/volume/sentiment
data. No database dependencies.
"""

import math
from datetime import date, timedelta

from worker.utils.technical_indicators import compute_macd, compute_rsi, compute_sma

from .models import (
    BASELINE_DAYS,
    MODERATE_THRESHOLD,
    PRICE_MOMENTUM_DAYS,
    RSI_LOOKBACK,
    RSI_PERIOD,
    SENTIMENT_HALF_LIFE_HOURS,
    STRONG_THRESHOLD,
    TREND_LOOKBACK,
    SentimentRow,
)


def compute_price_momentum_from_closes(closes: list[float]) -> float | None:
    """5-day price change, tanh-scaled to [-1, 1].

    Expects at least 6 closes (oldest first).
    """
    if len(closes) < 2:
        return None

    latest = closes[-1]
    # Use up to PRICE_MOMENTUM_DAYS back
    lookback = min(len(closes) - 1, PRICE_MOMENTUM_DAYS)
    oldest = closes[-(lookback + 1)]

    if oldest == 0:
        return None

    pct_change = (latest - oldest) / oldest
    return math.tanh(pct_change * 5)


def compute_volume_anomaly_from_data(
    closes: list[float], volumes: list[int]
) -> float | None:
    """Trading volume vs 20-day average, signed by price direction.

    Expects parallel closes and volumes arrays (oldest first), at least 3 entries.
    """
    if len(closes) < 3 or len(volumes) < 3:
        return None

    latest_volume = volumes[-1]
    latest_close = closes[-1]
    prev_close = closes[-2]

    if latest_volume is None or latest_volume == 0:
        return None

    # Average of previous volumes (excluding latest)
    prev_volumes = [v for v in volumes[:-1] if v and v > 0]
    if not prev_volumes:
        return None

    avg_volume = sum(prev_volumes) / len(prev_volumes)
    if avg_volume == 0:
        return None

    ratio = latest_volume / avg_volume
    magnitude = math.tanh(ratio - 1.0)

    if prev_close > 0:
        price_direction = 1.0 if latest_close >= prev_close else -1.0
    else:
        price_direction = 1.0

    return magnitude * price_direction


def compute_rsi_score_from_closes(closes: list[float]) -> float | None:
    """RSI(14) mapped to [-1, 1]: oversold = positive, overbought = negative.

    Expects at least 16 closes (oldest first).
    """
    if len(closes) < RSI_PERIOD + 2:
        return None

    rsi_values = compute_rsi(closes, period=RSI_PERIOD)
    latest_rsi = rsi_values[-1]
    if latest_rsi is None:
        return None

    centered = (50 - latest_rsi) / 50
    return math.tanh(centered * 2.5)


def compute_trend_score_from_closes(closes: list[float]) -> float | None:
    """Combined SMA crossover (60%) + MACD histogram (40%) trend score.

    Expects at least 52 closes (oldest first).
    """
    if len(closes) < 52:
        return None

    # SMA crossover component
    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    sma_score = 0.0
    if sma20[-1] is not None and sma50[-1] is not None and sma50[-1] != 0:
        sma_diff = (sma20[-1] - sma50[-1]) / sma50[-1]
        sma_score = math.tanh(sma_diff * 10)

    # MACD component
    macd_data = compute_macd(closes)
    macd_score = 0.0
    latest_macd = macd_data[-1]
    if latest_macd["histogram"] is not None and closes[-1] != 0:
        norm_hist = latest_macd["histogram"] / closes[-1]
        macd_score = math.tanh(norm_hist * 100)

    return 0.6 * sma_score + 0.4 * macd_score


def compute_sentiment_momentum_from_data(
    rows: list[SentimentRow], as_of_date: date
) -> float | None:
    """Exponentially weighted avg of daily sentiment, half-life 6h (~0.25 days).

    Looks back 2 days (48h equivalent in daily data).
    """
    if not rows:
        return None

    # Filter to rows within 2 days before as_of_date
    cutoff = as_of_date + timedelta(days=-2)
    recent = [r for r in rows if cutoff <= r.date <= as_of_date and r.article_count > 0]

    if not recent:
        return None

    # Convert daily sentiment to half-life decay (use days, half-life = 0.25 days = 6h)
    half_life_days = SENTIMENT_HALF_LIFE_HOURS / 24.0
    decay_rate = math.log(2) / half_life_days
    weighted_sum = 0.0
    weight_total = 0.0

    for row in recent:
        sentiment_value = row.avg_positive - row.avg_negative
        days_ago = (as_of_date - row.date).days
        weight = math.exp(-decay_rate * days_ago) * row.article_count
        weighted_sum += sentiment_value * weight
        weight_total += weight

    if weight_total == 0:
        return None

    return weighted_sum / weight_total


def compute_sentiment_volume_from_data(
    rows: list[SentimentRow], as_of_date: date
) -> float | None:
    """Article count on as_of_date vs 20-day baseline, signed by net sentiment.

    Mirrors calc_sentiment_volume in signal_generator.
    """
    if not rows:
        return None

    # Today's articles
    today_rows = [r for r in rows if r.date == as_of_date]
    today_count = sum(r.article_count for r in today_rows)
    today_net = 0.0
    if today_rows:
        total_articles = sum(r.article_count for r in today_rows)
        if total_articles > 0:
            today_net = sum(
                (r.avg_positive - r.avg_negative) * r.article_count for r in today_rows
            ) / total_articles

    if today_count == 0:
        return None

    # Baseline: last 20 days excluding today
    cutoff = as_of_date + timedelta(days=-BASELINE_DAYS)
    baseline_rows = [r for r in rows if cutoff <= r.date < as_of_date]
    baseline_total = sum(r.article_count for r in baseline_rows)
    baseline_days = max(len(set(r.date for r in baseline_rows)), 1)
    baseline_daily_avg = baseline_total / baseline_days

    if baseline_daily_avg == 0:
        ratio = min(today_count, 5.0)
    else:
        ratio = today_count / baseline_daily_avg

    magnitude = math.tanh(ratio - 1.0)
    direction_sign = 1.0 if today_net >= 0 else -1.0

    return magnitude * direction_sign


# ── Signal classification (mirrors signal_generator.py) ──


def classify_direction(composite: float) -> str:
    if composite > 0.01:
        return "bullish"
    elif composite < -0.01:
        return "bearish"
    return "neutral"


def classify_strength(composite: float) -> str:
    abs_score = abs(composite)
    if abs_score > STRONG_THRESHOLD:
        return "strong"
    elif abs_score > MODERATE_THRESHOLD:
        return "moderate"
    return "weak"
