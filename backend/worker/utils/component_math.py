"""Pure component-score math shared by live scoring and the backtester.

Live code queries the DB, then calls these functions. The backtester already
has in-memory arrays and calls the same functions. Do not reimplement tanh
scales, RSI mapping, or sentiment decay anywhere else.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from worker.utils.technical_indicators import compute_macd, compute_rsi, compute_sma

SENTIMENT_HALF_LIFE_HOURS = 6
BASELINE_DAYS = 20
PRICE_MOMENTUM_DAYS = 5
RSI_PERIOD = 14
RSI_LOOKBACK_DAYS = 30
TREND_LOOKBACK_DAYS = 60
PRICE_MOMENTUM_TANH_SCALE = 5.0
SMA_TANH_SCALE = 10.0
MACD_TANH_SCALE = 100.0
RSI_TANH_SCALE = 2.5
TREND_SMA_WEIGHT = 0.6
TREND_MACD_WEIGHT = 0.4
MIN_TREND_CLOSES = 52
MIN_RSI_CLOSES = RSI_PERIOD + 2  # 14-period RSI + warmup
VOLUME_SPIKE_CAP = 5.0


@dataclass(frozen=True)
class SentimentPoint:
    """One observation for exponential sentiment momentum."""

    value: float
    hours_ago: float
    weight: float = 1.0


def price_momentum(
    closes_oldest_first: Sequence[float],
    lookback_days: int = PRICE_MOMENTUM_DAYS,
) -> float | None:
    """Lookback-day price change, tanh-scaled to [-1, 1]. Oldest first."""
    if len(closes_oldest_first) < 2:
        return None

    latest = float(closes_oldest_first[-1])
    lookback = min(len(closes_oldest_first) - 1, lookback_days)
    oldest = float(closes_oldest_first[-(lookback + 1)])
    if oldest == 0:
        return None

    pct_change = (latest - oldest) / oldest
    return math.tanh(pct_change * PRICE_MOMENTUM_TANH_SCALE)


def volume_anomaly(
    closes_oldest_first: Sequence[float],
    volumes_oldest_first: Sequence[float],
) -> float | None:
    """Latest volume vs prior-day average, signed by price direction. Oldest first."""
    if len(closes_oldest_first) < 3 or len(volumes_oldest_first) < 3:
        return None

    latest_volume = volumes_oldest_first[-1]
    if latest_volume is None or latest_volume <= 0:
        return None

    latest_close = float(closes_oldest_first[-1])
    prev_close = float(closes_oldest_first[-2])

    prev_volumes = [v for v in volumes_oldest_first[:-1] if v and v > 0]
    if not prev_volumes:
        return None

    avg_volume = sum(prev_volumes) / len(prev_volumes)
    if avg_volume == 0:
        return None

    magnitude = math.tanh((latest_volume / avg_volume) - 1.0)
    if prev_close > 0:
        price_direction = 1.0 if latest_close >= prev_close else -1.0
    else:
        price_direction = 1.0
    return magnitude * price_direction


def rsi_score(
    closes_oldest_first: Sequence[float],
    period: int = RSI_PERIOD,
) -> float | None:
    """RSI mapped to [-1, 1]: oversold = positive, overbought = negative."""
    if len(closes_oldest_first) < period + 2:
        return None

    rsi_values = compute_rsi(list(closes_oldest_first), period=period)
    latest_rsi = rsi_values[-1]
    if latest_rsi is None:
        return None

    centered = (50 - latest_rsi) / 50
    return math.tanh(centered * RSI_TANH_SCALE)


def trend_score(closes_oldest_first: Sequence[float]) -> float | None:
    """SMA20/50 crossover (60%) + MACD histogram (40%). Oldest first."""
    if len(closes_oldest_first) < MIN_TREND_CLOSES:
        return None

    closes = list(closes_oldest_first)
    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    sma_component = 0.0
    if sma20[-1] is not None and sma50[-1] is not None and sma50[-1] != 0:
        sma_diff = (sma20[-1] - sma50[-1]) / sma50[-1]
        sma_component = math.tanh(sma_diff * SMA_TANH_SCALE)

    macd_data = compute_macd(closes)
    macd_component = 0.0
    latest_macd = macd_data[-1]
    if latest_macd["histogram"] is not None and closes[-1] != 0:
        norm_hist = latest_macd["histogram"] / closes[-1]
        macd_component = math.tanh(norm_hist * MACD_TANH_SCALE)

    return TREND_SMA_WEIGHT * sma_component + TREND_MACD_WEIGHT * macd_component


def exp_weighted_sentiment(
    points: Sequence[SentimentPoint],
    half_life_hours: float = SENTIMENT_HALF_LIFE_HOURS,
) -> float | None:
    """Exponentially weighted average of sentiment observations."""
    if not points:
        return None

    decay_rate = math.log(2) / half_life_hours
    weighted_sum = 0.0
    weight_total = 0.0
    for point in points:
        weight = math.exp(-decay_rate * point.hours_ago) * point.weight
        weighted_sum += point.value * weight
        weight_total += weight

    if weight_total == 0:
        return None
    return weighted_sum / weight_total


def signed_volume_ratio(
    unique_count: float,
    baseline_daily_avg: float,
    net_sentiment: float,
) -> float | None:
    """tanh(count / baseline - 1), signed by net sentiment. None if no events."""
    if unique_count == 0:
        return None

    if baseline_daily_avg == 0:
        ratio = min(unique_count, VOLUME_SPIKE_CAP)
    else:
        ratio = unique_count / baseline_daily_avg

    magnitude = math.tanh(ratio - 1.0)
    direction_sign = 1.0 if net_sentiment >= 0 else -1.0
    return magnitude * direction_sign
