"""Signal API endpoints — core signal CRUD and detail."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_current_user, get_db, get_stock_by_ticker
from app.models.article import Article
from app.models.sector import Sector
from app.models.sentiment import SentimentScore
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import PaginationMeta, PaginationParams, calc_total_pages, get_total_count
from app.schemas.signal import (
    LinkedArticle,
    PaginatedSignals,
    SignalDetailResponse,
    SignalOutcomeResponse,
    SignalResponse,
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


@router.get("/{ticker}", response_model=PaginatedSignals)
async def get_signal_history(
    ticker: str,
    pagination: PaginationParams = Depends(),
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
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return PaginatedSignals(
        data=[_to_response(s) for s in signals],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )


@router.get("", response_model=PaginatedSignals)
async def list_signals(
    pagination: PaginationParams = Depends(),
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
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return PaginatedSignals(
        data=[_to_response(s) for s in signals],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
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
        ml_score=float(signal.ml_score) if signal.ml_score else None,
        ml_direction=signal.ml_direction,
        ml_confidence=float(signal.ml_confidence) if signal.ml_confidence else None,
        generated_at=signal.generated_at,
        window_start=signal.window_start,
        window_end=signal.window_end,
    )
