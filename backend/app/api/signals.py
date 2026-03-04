"""Signal API endpoints."""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.schemas.signal import PaginatedSignals, PaginationMeta, SignalResponse

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


@router.get("/{ticker}", response_model=PaginatedSignals)
async def get_signal_history(
    ticker: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get signal history for a specific ticker."""
    stock = await _get_stock(ticker, db)

    base_query = select(Signal).where(Signal.stock_id == stock.id)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

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
            total_pages=max(1, math.ceil(total / per_page)),
        ),
    )


@router.get("", response_model=PaginatedSignals)
async def list_signals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    direction: str | None = Query(None),
    strength: str | None = Query(None),
    ticker: str | None = Query(None),
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

    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

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
            total_pages=max(1, math.ceil(total / per_page)),
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
        price_score=float(signal.price_score) if signal.price_score else None,
        volume_score=float(signal.volume_score) if signal.volume_score else None,
        article_count=signal.article_count,
        reasoning=signal.reasoning,
        generated_at=signal.generated_at,
        window_start=signal.window_start,
        window_end=signal.window_end,
    )


async def _get_stock(ticker: str, db: AsyncSession) -> Stock:
    result = await db.execute(
        select(Stock).where(func.upper(Stock.ticker) == ticker.upper())
    )
    stock = result.scalar_one_or_none()
    if not stock:
        raise NotFoundError(f"Stock {ticker} not found")
    return stock
