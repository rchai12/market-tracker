"""Signal component adapters for the backtesting engine.

Thin wrappers over worker.utils.component_math so engine/tests keep stable names.
Daily sentiment rows are mapped onto the shared hourly decay kernel.
"""

from datetime import date, timedelta

from worker.utils.component_math import (
    BASELINE_DAYS,
    SENTIMENT_HALF_LIFE_HOURS,
    SentimentPoint,
    exp_weighted_sentiment,
    price_momentum,
    rsi_score,
    signed_volume_ratio,
    trend_score,
    volume_anomaly,
)
from worker.utils.signal_formula import classify_direction, classify_strength

from .models import SentimentRow

__all__ = [
    "classify_direction",
    "classify_strength",
    "compute_price_momentum_from_closes",
    "compute_rsi_score_from_closes",
    "compute_sentiment_momentum_from_data",
    "compute_sentiment_volume_from_data",
    "compute_trend_score_from_closes",
    "compute_volume_anomaly_from_data",
]


def compute_price_momentum_from_closes(closes: list[float]) -> float | None:
    """5-day price change, tanh-scaled to [-1, 1]. Oldest first."""
    return price_momentum(closes)


def compute_volume_anomaly_from_data(
    closes: list[float], volumes: list[int]
) -> float | None:
    """Trading volume vs 20-day average, signed by price direction. Oldest first."""
    return volume_anomaly(closes, volumes)


def compute_rsi_score_from_closes(closes: list[float]) -> float | None:
    """RSI(14) mapped to [-1, 1]: oversold = positive, overbought = negative."""
    return rsi_score(closes)


def compute_trend_score_from_closes(closes: list[float]) -> float | None:
    """Combined SMA crossover (60%) + MACD histogram (40%) trend score."""
    return trend_score(closes)


def compute_sentiment_momentum_from_data(
    rows: list[SentimentRow], as_of_date: date
) -> float | None:
    """Exponentially weighted avg of daily sentiment (6h half-life in day units)."""
    if not rows:
        return None

    cutoff = as_of_date + timedelta(days=-2)
    recent = [r for r in rows if cutoff <= r.date <= as_of_date and r.article_count > 0]
    if not recent:
        return None

    points = [
        SentimentPoint(
            value=row.avg_positive - row.avg_negative,
            hours_ago=(as_of_date - row.date).days * 24.0,
            weight=float(row.article_count),
        )
        for row in recent
    ]
    return exp_weighted_sentiment(points, half_life_hours=SENTIMENT_HALF_LIFE_HOURS)


def compute_sentiment_volume_from_data(
    rows: list[SentimentRow], as_of_date: date
) -> float | None:
    """Article count on as_of_date vs 20-day baseline, signed by net sentiment."""
    if not rows:
        return None

    today_rows = [r for r in rows if r.date == as_of_date]
    today_count = sum(r.article_count for r in today_rows)
    today_net = 0.0
    if today_rows:
        total_articles = sum(r.article_count for r in today_rows)
        if total_articles > 0:
            today_net = sum(
                (r.avg_positive - r.avg_negative) * r.article_count for r in today_rows
            ) / total_articles

    cutoff = as_of_date + timedelta(days=-BASELINE_DAYS)
    baseline_rows = [r for r in rows if cutoff <= r.date < as_of_date]
    baseline_total = sum(r.article_count for r in baseline_rows)
    baseline_days = max(len(set(r.date for r in baseline_rows)), 1)
    baseline_daily_avg = baseline_total / baseline_days

    return signed_volume_ratio(today_count, baseline_daily_avg, today_net)
