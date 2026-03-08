"""Signal accuracy and methodology API endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_current_user, get_db, get_stock_by_ticker
from app.models.sector import Sector
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from app.models.user import User
from app.schemas.signal import (
    AccuracyBucket,
    AccuracyDistribution,
    AccuracyTrendPoint,
    SignalAccuracyResponse,
    SignalWeightsResponse,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/accuracy", response_model=list[SignalAccuracyResponse])
async def get_signal_accuracy(
    window_days: int = Query(5, description="Evaluation window: 1, 3, or 5"),
    sector: str | None = Query(None),
    days: int = Query(90, ge=7, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get signal accuracy metrics, optionally filtered by sector."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(
            Signal.direction,
            SignalOutcome.is_correct,
            SignalOutcome.price_change_pct,
        )
        .join(Signal, SignalOutcome.signal_id == Signal.id)
        .join(Stock, Signal.stock_id == Stock.id)
        .where(SignalOutcome.window_days == window_days)
        .where(SignalOutcome.evaluated_at >= cutoff)
        .where(Signal.direction.in_(["bullish", "bearish"]))
    )

    scope = "global"
    if sector:
        query = query.join(Sector, Stock.sector_id == Sector.id).where(func.lower(Sector.name) == sector.lower())
        scope = f"sector:{sector}"

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return []

    return [_compute_accuracy(rows, scope, window_days)]


@router.get("/accuracy/trend", response_model=list[AccuracyTrendPoint])
async def get_accuracy_trend(
    window_days: int = Query(5, description="Evaluation window: 1, 3, or 5"),
    sector: str | None = Query(None),
    bucket: str = Query("week", description="Bucket size: week or month"),
    days: int = Query(180, ge=30, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get accuracy trend over time in weekly or monthly buckets."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(
            SignalOutcome.is_correct,
            SignalOutcome.evaluated_at,
        )
        .join(Signal, SignalOutcome.signal_id == Signal.id)
        .join(Stock, Signal.stock_id == Stock.id)
        .where(SignalOutcome.window_days == window_days)
        .where(SignalOutcome.evaluated_at >= cutoff)
        .where(Signal.direction.in_(["bullish", "bearish"]))
    )

    if sector:
        query = query.join(Sector, Stock.sector_id == Sector.id).where(func.lower(Sector.name) == sector.lower())

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return []

    # Group into buckets
    bucket_days = 7 if bucket == "week" else 30
    buckets: dict[datetime, dict] = {}

    for row in rows:
        evaluated = row.evaluated_at
        # Normalize to bucket start
        days_since_cutoff = (evaluated - cutoff).days
        bucket_index = days_since_cutoff // bucket_days
        bucket_start = cutoff + timedelta(days=bucket_index * bucket_days)
        bucket_end = bucket_start + timedelta(days=bucket_days)

        key = bucket_start
        if key not in buckets:
            buckets[key] = {"start": bucket_start, "end": bucket_end, "total": 0, "correct": 0}
        buckets[key]["total"] += 1
        if row.is_correct:
            buckets[key]["correct"] += 1

    return [
        AccuracyTrendPoint(
            period_start=b["start"],
            period_end=b["end"],
            total=b["total"],
            correct=b["correct"],
            accuracy_pct=round(b["correct"] / b["total"] * 100, 1) if b["total"] else 0,
        )
        for b in sorted(buckets.values(), key=lambda x: x["start"])
    ]


@router.get("/accuracy/distribution", response_model=AccuracyDistribution)
async def get_accuracy_distribution(
    window_days: int = Query(5, description="Evaluation window: 1, 3, or 5"),
    days: int = Query(90, ge=7, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get accuracy breakdown by strength and direction."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(
            Signal.direction,
            Signal.strength,
            SignalOutcome.is_correct,
            SignalOutcome.price_change_pct,
        )
        .join(Signal, SignalOutcome.signal_id == Signal.id)
        .where(SignalOutcome.window_days == window_days)
        .where(SignalOutcome.evaluated_at >= cutoff)
        .where(Signal.direction.in_(["bullish", "bearish"]))
    )

    result = await db.execute(query)
    rows = result.all()

    def _build_buckets(rows_list: list, key_fn) -> list[AccuracyBucket]:
        groups: dict[str, list] = {}
        for r in rows_list:
            key = key_fn(r)
            groups.setdefault(key, []).append(r)

        buckets = []
        for label, group in sorted(groups.items()):
            total = len(group)
            correct = sum(1 for r in group if r.is_correct)
            returns = [float(r.price_change_pct) for r in group]
            buckets.append(
                AccuracyBucket(
                    label=label,
                    total=total,
                    correct=correct,
                    accuracy_pct=round(correct / total * 100, 1) if total else 0,
                    avg_return_pct=round(sum(returns) / len(returns) * 100, 3) if returns else 0,
                )
            )
        return buckets

    return AccuracyDistribution(
        by_strength=_build_buckets(rows, lambda r: r.strength),
        by_direction=_build_buckets(rows, lambda r: r.direction),
    )


@router.get("/accuracy/{ticker}", response_model=list[SignalAccuracyResponse])
async def get_ticker_accuracy(
    ticker: str,
    days: int = Query(90, ge=7, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get accuracy metrics for a specific ticker across all windows."""
    stock = await get_stock_by_ticker(ticker, db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    results = []
    for window in [1, 3, 5]:
        query = (
            select(
                Signal.direction,
                SignalOutcome.is_correct,
                SignalOutcome.price_change_pct,
            )
            .join(Signal, SignalOutcome.signal_id == Signal.id)
            .where(Signal.stock_id == stock.id)
            .where(SignalOutcome.window_days == window)
            .where(SignalOutcome.evaluated_at >= cutoff)
            .where(Signal.direction.in_(["bullish", "bearish"]))
        )
        result = await db.execute(query)
        rows = result.all()
        if rows:
            results.append(_compute_accuracy(rows, f"ticker:{ticker.upper()}", window))

    return results


@router.get("/weights", response_model=list[SignalWeightsResponse])
async def get_signal_weights(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active signal weights (per-sector and global fallback)."""
    result = await db.execute(
        select(SignalWeight)
        .options(joinedload(SignalWeight.sector))
        .order_by(SignalWeight.sector_id.asc().nullsfirst())
    )
    weights = result.unique().scalars().all()

    return [
        SignalWeightsResponse(
            sector_name=w.sector.name if w.sector else None,
            sentiment_momentum=float(w.sentiment_momentum),
            sentiment_volume=float(w.sentiment_volume),
            price_momentum=float(w.price_momentum),
            volume_anomaly=float(w.volume_anomaly),
            rsi=float(w.rsi),
            trend=float(w.trend),
            sample_count=w.sample_count,
            accuracy_pct=float(w.accuracy_pct) if w.accuracy_pct else None,
            computed_at=w.computed_at,
            source="sector" if w.sector_id else "global",
        )
        for w in weights
    ]


def _compute_accuracy(rows: list, scope: str, window_days: int) -> SignalAccuracyResponse:
    """Compute accuracy metrics from a list of (direction, is_correct, price_change_pct) rows."""
    total = len(rows)
    correct = sum(1 for r in rows if r.is_correct)

    correct_returns = [float(r.price_change_pct) for r in rows if r.is_correct]
    wrong_returns = [float(r.price_change_pct) for r in rows if not r.is_correct]

    bullish_rows = [r for r in rows if r.direction == "bullish"]
    bearish_rows = [r for r in rows if r.direction == "bearish"]

    bullish_acc = (
        round(sum(1 for r in bullish_rows if r.is_correct) / len(bullish_rows) * 100, 1)
        if bullish_rows
        else None
    )
    bearish_acc = (
        round(sum(1 for r in bearish_rows if r.is_correct) / len(bearish_rows) * 100, 1)
        if bearish_rows
        else None
    )

    return SignalAccuracyResponse(
        scope=scope,
        window_days=window_days,
        total_evaluated=total,
        correct_count=correct,
        accuracy_pct=round(correct / total * 100, 1) if total else 0,
        avg_return_correct=round(sum(correct_returns) / len(correct_returns) * 100, 3) if correct_returns else 0,
        avg_return_wrong=round(sum(wrong_returns) / len(wrong_returns) * 100, 3) if wrong_returns else 0,
        bullish_accuracy_pct=bullish_acc,
        bearish_accuracy_pct=bearish_acc,
    )
