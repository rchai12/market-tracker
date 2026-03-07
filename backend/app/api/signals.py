"""Signal API endpoints."""

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
from app.schemas.common import PaginationMeta, calc_total_pages, get_total_count
from app.schemas.signal import PaginatedSignals, SignalAccuracyResponse, SignalResponse, SignalWeightsResponse

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/latest", response_model=list[SignalResponse])
async def get_latest_signals(
    limit: int = Query(20, ge=1, le=100),
    min_strength: str | None = Query(None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent signals across all stocks. For dashboard feed."""
    query = (
        select(Signal)
        .options(joinedload(Signal.stock))
        .order_by(Signal.generated_at.desc())
    )

    if min_strength:
        query = query.where(Signal.strength == min_strength)

    query = query.limit(limit)
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return [_to_response(s) for s in signals]


@router.get("/accuracy", response_model=list[SignalAccuracyResponse])
async def get_signal_accuracy(
    window_days: int = Query(5, description="Evaluation window: 1, 3, or 5"),
    sector: str | None = Query(None),
    days: int = Query(90, ge=7, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get signal accuracy metrics, optionally filtered by sector."""
    from datetime import datetime, timedelta, timezone

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


@router.get("/accuracy/{ticker}", response_model=list[SignalAccuracyResponse])
async def get_ticker_accuracy(
    ticker: str,
    days: int = Query(90, ge=7, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get accuracy metrics for a specific ticker across all windows."""
    from datetime import datetime, timedelta, timezone

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
            sample_count=w.sample_count,
            accuracy_pct=float(w.accuracy_pct) if w.accuracy_pct else None,
            computed_at=w.computed_at,
            source="sector" if w.sector_id else "global",
        )
        for w in weights
    ]


@router.get("/{ticker}", response_model=PaginatedSignals)
async def get_signal_history(
    ticker: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get signal history for a specific ticker."""
    stock = await get_stock_by_ticker(ticker, db)

    base_query = select(Signal).where(Signal.stock_id == stock.id)

    total = await get_total_count(db, base_query)

    query = (
        base_query
        .options(joinedload(Signal.stock))
        .order_by(Signal.generated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return PaginatedSignals(
        data=[_to_response(s) for s in signals],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=calc_total_pages(total, per_page),
        ),
    )


@router.get("", response_model=PaginatedSignals)
async def list_signals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    direction: str | None = Query(None),
    strength: str | None = Query(None),
    ticker: str | None = Query(None),
    sector: str | None = Query(None, description="Filter by sector name"),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all signals with optional filters and pagination."""
    base_query = select(Signal)

    if direction:
        base_query = base_query.where(Signal.direction == direction)

    if strength:
        base_query = base_query.where(Signal.strength == strength)

    if ticker:
        base_query = base_query.join(Stock).where(
            func.upper(Stock.ticker) == ticker.upper()
        )

    if sector:
        if ticker:
            # Stock already joined
            base_query = base_query.join(Sector).where(func.lower(Sector.name) == sector.lower())
        else:
            base_query = base_query.join(Stock).join(Sector).where(func.lower(Sector.name) == sector.lower())

    total = await get_total_count(db, base_query)

    query = (
        base_query
        .options(joinedload(Signal.stock))
        .order_by(Signal.generated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return PaginatedSignals(
        data=[_to_response(s) for s in signals],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=calc_total_pages(total, per_page),
        ),
    )


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


def _to_response(signal: Signal) -> SignalResponse:
    return SignalResponse(
        id=signal.id,
        stock_id=signal.stock_id,
        ticker=signal.stock.ticker if signal.stock else "???",
        company_name=signal.stock.company_name if signal.stock else "Unknown",
        direction=signal.direction,
        strength=signal.strength,
        composite_score=float(signal.composite_score),
        sentiment_score=float(signal.sentiment_score) if signal.sentiment_score else None,
        price_score=float(signal.price_score) if signal.price_score else None,
        volume_score=float(signal.volume_score) if signal.volume_score else None,
        article_count=signal.article_count,
        reasoning=signal.reasoning,
        generated_at=signal.generated_at,
        window_start=signal.window_start,
        window_end=signal.window_end,
    )
