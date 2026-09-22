"""Pure aggregations for daily-view accuracy observability (Phase 24c).

API handlers query rows, then call these so the headline metric, calibration
buckets, weekly trend, and sector/regime tables cannot drift independently.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from worker.utils.daily_aggregation import MIN_CONVICTION

MIN_VIEWS_FOR_CONFIDENCE = 50
MIN_CALIBRATION_BUCKET = 10
MIN_SECTOR_COUNT = 5

CALIBRATION_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("Low", 0.20, 0.35),
    ("Medium", 0.35, 0.50),
    ("High", 0.50, 0.65),
    ("Very High", 0.65, 1.0),
)


@dataclass(frozen=True)
class AccuracyRow:
    conviction: float
    is_correct: bool | None
    excess_return: float | None
    trading_date: date | None = None
    sector: str | None = None
    regime: str | None = None


def ratio_to_pct(value: float | None) -> float:
    """Stored excess/price change is a ratio (0.0124); API/UI use percent (1.24)."""
    if value is None:
        return 0.0
    return round(float(value) * 100.0, 2)


def conviction_bucket(conviction: float) -> str | None:
    """Assign a calibration label. Bounds are [min, max) except Very High which is inclusive."""
    if conviction < CALIBRATION_BUCKETS[0][1]:
        return None
    for label, low, high in CALIBRATION_BUCKETS[:-1]:
        if low <= conviction < high:
            return label
    return CALIBRATION_BUCKETS[-1][0]


def iso_week_start(day: date) -> date:
    """Monday of the ISO week containing *day*."""
    return day - timedelta(days=day.weekday())


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def summarize_accuracy(rows: list[AccuracyRow], *, total_views: int | None = None) -> dict:
    """Headline daily-view accuracy used by the optimizer/ML `is_correct` labels."""
    evaluated = [row for row in rows if row.is_correct is not None]
    evaluated_views = len(evaluated)
    correct = sum(1 for row in evaluated if row.is_correct)
    incorrect = [row for row in evaluated if not row.is_correct]
    correct_rows = [row for row in evaluated if row.is_correct]
    excess_all = [float(row.excess_return) for row in evaluated if row.excess_return is not None]
    excess_ok = [float(row.excess_return) for row in correct_rows if row.excess_return is not None]
    excess_bad = [float(row.excess_return) for row in incorrect if row.excess_return is not None]
    accuracy_pct = round(correct / evaluated_views * 100.0, 1) if evaluated_views else 0.0
    return {
        "total_views": total_views if total_views is not None else len(rows),
        "evaluated_views": evaluated_views,
        "correct": correct,
        "accuracy_pct": accuracy_pct,
        "avg_conviction": round(mean([float(row.conviction) for row in evaluated]), 2),
        "avg_excess_return_correct": ratio_to_pct(mean(excess_ok) if excess_ok else None),
        "avg_excess_return_incorrect": ratio_to_pct(mean(excess_bad) if excess_bad else None),
        "avg_excess_return_all": ratio_to_pct(mean(excess_all) if excess_all else None),
        "insufficient_data": evaluated_views < MIN_VIEWS_FOR_CONFIDENCE,
        "min_views_for_confidence": MIN_VIEWS_FOR_CONFIDENCE,
    }


def aggregate_calibration(rows: list[AccuracyRow]) -> list[dict]:
    """Always return the four conviction buckets (empty buckets have count 0)."""
    grouped: dict[str, list[AccuracyRow]] = {label: [] for label, _, _ in CALIBRATION_BUCKETS}
    for row in rows:
        if row.is_correct is None:
            continue
        label = conviction_bucket(row.conviction)
        if label is None:
            continue
        grouped[label].append(row)
    out: list[dict] = []
    for label, low, high in CALIBRATION_BUCKETS:
        bucket_rows = grouped[label]
        n = len(bucket_rows)
        correct = sum(1 for row in bucket_rows if row.is_correct)
        excess = [float(row.excess_return) for row in bucket_rows if row.excess_return is not None]
        out.append(
            {
                "label": label,
                "min_conviction": low,
                "max_conviction": high,
                "count": n,
                "accuracy_pct": round(correct / n * 100.0, 1) if n else 0.0,
                "avg_excess_return": ratio_to_pct(mean(excess) if excess else None),
            }
        )
    return out


def calibration_is_thin(buckets: list[dict], min_count: int = MIN_CALIBRATION_BUCKET) -> bool:
    """True when any bucket has fewer than *min_count* views (hide the chart)."""
    if not buckets:
        return True
    return any(int(bucket["count"]) < min_count for bucket in buckets)


def aggregate_weekly_trend(rows: list[AccuracyRow]) -> list[dict]:
    grouped: dict[date, list[AccuracyRow]] = defaultdict(list)
    for row in rows:
        if row.is_correct is None or row.trading_date is None:
            continue
        grouped[iso_week_start(row.trading_date)].append(row)
    out: list[dict] = []
    for week_start in sorted(grouped):
        week_rows = grouped[week_start]
        n = len(week_rows)
        correct = sum(1 for row in week_rows if row.is_correct)
        excess = [float(row.excess_return) for row in week_rows if row.excess_return is not None]
        out.append(
            {
                "week_start": week_start,
                "view_count": n,
                "accuracy_pct": round(correct / n * 100.0, 1) if n else 0.0,
                "avg_conviction": round(mean([float(row.conviction) for row in week_rows]), 2),
                "avg_excess_return": ratio_to_pct(mean(excess) if excess else None),
            }
        )
    return out


def aggregate_by_label(rows: list[AccuracyRow], field: str) -> list[dict]:
    grouped: dict[str, list[AccuracyRow]] = defaultdict(list)
    for row in rows:
        if row.is_correct is None:
            continue
        label = getattr(row, field, None)
        if not label:
            continue
        grouped[str(label)].append(row)
    out: list[dict] = []
    for name in sorted(grouped):
        group_rows = grouped[name]
        n = len(group_rows)
        correct = sum(1 for row in group_rows if row.is_correct)
        excess = [float(row.excess_return) for row in group_rows if row.excess_return is not None]
        item = {
            "count": n,
            "accuracy_pct": round(correct / n * 100.0, 1) if n else 0.0,
            "avg_excess_return": ratio_to_pct(mean(excess) if excess else None),
            "avg_conviction": round(mean([float(row.conviction) for row in group_rows]), 2),
        }
        item[field] = name
        out.append(item)
    return out


def visible_group_rows(rows: list[dict], min_count: int = MIN_SECTOR_COUNT) -> list[dict]:
    return [row for row in rows if int(row["count"]) >= min_count]


# Re-export so API filters stay aligned with the learning gate.
DEFAULT_MIN_CONVICTION = MIN_CONVICTION
