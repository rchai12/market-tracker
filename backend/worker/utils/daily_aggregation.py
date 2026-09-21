"""Daily net-view aggregation for learning (Phase 24 / 24b).

Pure helpers: trading-date assignment, net score, conviction, time buckets,
recency weights, excess-return scoring, and proportional component credit.
DB/Celery stay in tasks.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Sequence
from zoneinfo import ZoneInfo

MIN_CONVICTION = 0.20
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
ET = ZoneInfo("America/New_York")
RECENCY_LAMBDA = 0.15  # half-life ≈ 4.6 hours
BUCKET_BOUNDARIES_ET = (time(9, 30), time(13, 30), time(16, 0))

SECTOR_BENCHMARK = {
    "Energy": "XLE",
    "Financials": "XLF",
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Market ETFs": None,
}

FEATURE_FIELDS = (
    "sentiment_score",
    "sentiment_volume_score",
    "price_score",
    "volume_score",
    "rsi_score",
    "trend_score",
)


def direction_sign(direction: str) -> float:
    if direction == "bullish":
        return 1.0
    if direction == "bearish":
        return -1.0
    return 0.0


def trading_date_lower_bound(generated_at: datetime) -> date:
    """Earliest calendar date of the next market close this signal predicts.

    Weekdays before 16:00 ET (including pre-market) predict that day's close.
    After hours or weekend → tomorrow, then resolved against market_data_daily
    to skip holidays.
    """
    et = generated_at.astimezone(ET) if generated_at.tzinfo else generated_at.replace(tzinfo=ET)
    weekday = et.weekday()
    clock = et.time()
    # Weekday before the 16:00 ET close (including pre-market) → same-day close.
    if weekday < 5 and clock < MARKET_CLOSE:
        return et.date()
    return et.date() + timedelta(days=1)


def in_cash_session(generated_at: datetime) -> bool:
    """True during the 09:30–16:00 ET Mon–Fri cash session."""
    et = generated_at.astimezone(ET) if generated_at.tzinfo else generated_at.replace(tzinfo=ET)
    return et.weekday() < 5 and MARKET_OPEN <= et.time() < MARKET_CLOSE


def pick_trading_date(floor: date, available_dates: Sequence[date]) -> date | None:
    """First session date on or after *floor*. None if the calendar is empty."""
    future = [d for d in available_dates if d >= floor]
    if not future:
        return None
    return min(future)


@dataclass(frozen=True)
class NetView:
    net_score: float
    conviction: float
    direction: str
    signal_count: int
    weight_total: float


def compute_net_view(signals: Sequence[object], trading_date: date | None = None) -> NetView | None:
    """Magnitude- and recency-weighted net direction from per-signal composites.

    Each signal votes ``abs(composite) * recency * sign(direction)``. Neutrals
    contribute 0 to the numerator. Returns None when no magnitude remains.
    """
    if not signals:
        return None
    weighted_sum = 0.0
    weight_total = 0.0
    counted = 0
    for signal in signals:
        weight = signal_vote_weight(signal, trading_date)
        if weight == 0:
            continue
        counted += 1
        weighted_sum += weight * direction_sign(getattr(signal, "direction", "") or "")
        weight_total += weight
    if weight_total == 0:
        return None
    net_score = weighted_sum / weight_total
    return NetView(
        net_score=net_score,
        conviction=abs(net_score),
        direction="bullish" if net_score > 0 else "bearish",
        signal_count=counted,
        weight_total=weight_total,
    )


def signal_vote_weight(signal: object, trading_date: date | None = None) -> float:
    """``abs(composite)`` scaled by recency when *trading_date* and ``generated_at`` exist."""
    composite = getattr(signal, "composite_score", None)
    if composite is None:
        return 0.0
    mag = abs(float(composite))
    if mag == 0:
        return 0.0
    generated_at = getattr(signal, "generated_at", None)
    if trading_date is None or generated_at is None:
        return mag
    return mag * recency_weight(generated_at, trading_date)


def recency_weight(generated_at: datetime, trading_date: date) -> float:
    """1.0 at the session close, exponential decay for earlier signals."""
    et = generated_at.astimezone(ET) if generated_at.tzinfo else generated_at.replace(tzinfo=ET)
    close_dt = datetime.combine(trading_date, MARKET_CLOSE, tzinfo=ET)
    hours_before = max(0.0, (close_dt - et).total_seconds() / 3600.0)
    return math.exp(-RECENCY_LAMBDA * hours_before)


def signal_bucket(generated_at: datetime) -> str:
    """Map a timestamp to pre_market / morning / afternoon (ET)."""
    et = generated_at.astimezone(ET) if generated_at.tzinfo else generated_at.replace(tzinfo=ET)
    clock = et.time()
    pre_market_end, morning_end, _close = BUCKET_BOUNDARIES_ET
    if clock < pre_market_end:
        return "pre_market"
    if clock < morning_end:
        return "morning"
    return "afternoon"


def bucket_signals(signals: Sequence[object]) -> list:
    """One signal per 4-hour ET bucket: highest |composite_score| wins."""
    buckets: dict[str, object] = {}
    for signal in signals:
        composite = getattr(signal, "composite_score", None)
        if composite is None:
            continue
        generated_at = getattr(signal, "generated_at", None)
        bucket = signal_bucket(generated_at) if generated_at is not None else "afternoon"
        existing = buckets.get(bucket)
        if existing is None or abs(float(composite)) > abs(float(getattr(existing, "composite_score", 0) or 0)):
            buckets[bucket] = signal
    return list(buckets.values())


def outcome_is_correct(direction: str, scored_return: float) -> bool:
    return (direction == "bullish" and scored_return > 0) or (
        direction == "bearish" and scored_return < 0
    )


def excess_return_pct(stock_return: float, sector_return: float | None) -> float | None:
    """Stock minus sector ETF; None when there is no benchmark."""
    if sector_return is None:
        return None
    return float(stock_return) - float(sector_return)


def majority_regime(signals: Sequence[object]) -> str | None:
    labels = [getattr(s, "market_regime", None) for s in signals]
    labels = [label for label in labels if label]
    if not labels:
        return None
    return Counter(labels).most_common(1)[0][0]


def magnitude_share(composite: float, weight_total: float) -> float:
    if weight_total <= 0:
        return 0.0
    return abs(float(composite)) / weight_total


def aggregate_feature_vector(signals: Sequence[object]) -> list[float]:
    """Weighted mean of the 6 ML features by ``abs(composite_score)``."""
    totals = [0.0] * len(FEATURE_FIELDS)
    weight_total = 0.0
    for signal in signals:
        composite = getattr(signal, "composite_score", None)
        if composite is None:
            continue
        mag = abs(float(composite))
        if mag == 0:
            continue
        weight_total += mag
        for i, field in enumerate(FEATURE_FIELDS):
            raw = getattr(signal, field, None)
            totals[i] += mag * (float(raw) if raw is not None else 0.0)
    if weight_total == 0:
        return [0.0] * len(FEATURE_FIELDS)
    return [part / weight_total for part in totals]


def scale_outcome_pct(price_change_pct: float, share: float) -> float:
    """Scale a view-level return so ``abs(pct)`` equals that signal's credit."""
    return float(price_change_pct) * float(share)


def expand_view_credits(
    signals: Sequence[object],
    price_change_pct: float,
    is_correct: bool,
    trading_date: date | None = None,
) -> list[SimpleNamespace]:
    """One credit-row per contributing signal, return scaled by vote-weight share."""
    net = compute_net_view(signals, trading_date)
    if net is None or net.weight_total <= 0:
        return []
    rows: list[SimpleNamespace] = []
    for signal in signals:
        weight = signal_vote_weight(signal, trading_date)
        if weight == 0:
            continue
        share = weight / net.weight_total
        rows.append(
            SimpleNamespace(
                sentiment_score=getattr(signal, "sentiment_score", None),
                price_score=getattr(signal, "price_score", None),
                volume_score=getattr(signal, "volume_score", None),
                options_score=getattr(signal, "options_score", None),
                earnings_score=getattr(signal, "earnings_score", None),
                analyst_score=getattr(signal, "analyst_score", None),
                insider_score=getattr(signal, "insider_score", None),
                direction=getattr(signal, "direction", None),
                is_correct=is_correct,
                price_change_pct=scale_outcome_pct(price_change_pct, share),
                share=share,
            )
        )
    return rows
