"""Signal API endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_current_user, get_db, get_stock_by_ticker
from app.models.article import Article
from app.models.sector import Sector
from app.models.sentiment import SentimentScore
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import PaginationMeta, calc_total_pages, get_total_count
from app.schemas.signal import (
    AccuracyBucket,
    AccuracyDistribution,
    AccuracyTrendPoint,
    LinkedArticle,
    PaginatedSignals,
    SignalAccuracyResponse,
    SignalDetailResponse,
    SignalOutcomeResponse,
    SignalResponse,
    SignalWeightsResponse,
)

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


@router.get("/detail/{signal_id}", response_model=SignalDetailResponse)
async def get_signal_detail(
    signal_id: int,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full signal detail with outcomes and linked articles."""
    result = await db.execute(
        select(Signal)
        .options(joinedload(Signal.stock), joinedload(Signal.outcomes))
        .where(Signal.id == signal_id)
    )
    signal = result.unique().scalars().first()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Build outcomes
    outcomes = [
        SignalOutcomeResponse(
            window_days=o.window_days,
            price_change_pct=float(o.price_change_pct),
            is_correct=o.is_correct,
            evaluated_at=o.evaluated_at,
        )
        for o in sorted(signal.outcomes, key=lambda o: o.window_days)
    ]

    # Find linked articles via sentiment_scores in signal's time window
    article_query = (
        select(
            Article.id,
            Article.title,
            Article.source,
            Article.source_url,
            Article.published_at,
            SentimentScore.label,
            (SentimentScore.positive_score - SentimentScore.negative_score).label("net_sentiment"),
        )
        .join(SentimentScore, Article.id == SentimentScore.article_id)
        .where(SentimentScore.stock_id == signal.stock_id)
        .where(SentimentScore.processed_at >= signal.window_start)
        .where(SentimentScore.processed_at <= signal.window_end)
        .order_by(Article.published_at.desc().nullslast())
        .limit(50)
    )
    article_result = await db.execute(article_query)
    article_rows = article_result.all()

    linked_articles = [
        LinkedArticle(
            id=row.id,
            title=row.title,
            source=row.source,
            url=row.source_url,
            published_at=row.published_at,
            sentiment_label=row.label,
            sentiment_score=round(float(row.net_sentiment), 4) if row.net_sentiment is not None else None,
        )
        for row in article_rows
    ]

    return SignalDetailResponse(
        signal=_to_response(signal),
        outcomes=outcomes,
        linked_articles=linked_articles,
    )


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
        sentiment_volume_score=float(signal.sentiment_volume_score) if signal.sentiment_volume_score else None,
        price_score=float(signal.price_score) if signal.price_score else None,
        volume_score=float(signal.volume_score) if signal.volume_score else None,
        rsi_score=float(signal.rsi_score) if signal.rsi_score else None,
        trend_score=float(signal.trend_score) if signal.trend_score else None,
        article_count=signal.article_count,
        reasoning=signal.reasoning,
        generated_at=signal.generated_at,
        window_start=signal.window_start,
        window_end=signal.window_end,
    )
