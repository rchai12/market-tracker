"""Daily net-view aggregation for learning (Phase 24).

Pure helpers: trading-date assignment, net score, conviction, feature
aggregation, and proportional component credit. DB/Celery stay in tasks.
"""

from __future__ import annotations

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


def compute_net_view(signals: Sequence[object]) -> NetView | None:
    """Magnitude-weighted net direction from per-signal composites.

    Each signal votes ``abs(composite) * sign(direction)``. Neutrals contribute
    0 to the numerator. Returns None when no magnitude remains.
    """
    if not signals:
        return None
    weighted_sum = 0.0
    weight_total = 0.0
    for signal in signals:
        composite = getattr(signal, "composite_score", None)
        if composite is None:
            continue
        mag = abs(float(composite))
        if mag == 0:
            continue
        weighted_sum += mag * direction_sign(getattr(signal, "direction", "") or "")
        weight_total += mag
    if weight_total == 0:
        return None
    net_score = weighted_sum / weight_total
    return NetView(
        net_score=net_score,
        conviction=abs(net_score),
        direction="bullish" if net_score > 0 else "bearish",
        signal_count=len(signals),
        weight_total=weight_total,
    )


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
) -> list[SimpleNamespace]:
    """One credit-row per contributing signal, return scaled by magnitude share."""
    net = compute_net_view(signals)
    if net is None or net.weight_total <= 0:
        return []
    rows: list[SimpleNamespace] = []
    for signal in signals:
        composite = getattr(signal, "composite_score", None)
        if composite is None:
            continue
        mag = abs(float(composite))
        if mag == 0:
            continue
        share = magnitude_share(mag, net.weight_total)
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
