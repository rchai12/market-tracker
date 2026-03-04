from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db
from app.models.market_data import MarketDataDaily, MarketDataIntraday
from app.models.stock import Stock
from app.models.user import User
from app.schemas.market_data import MarketDataDailyResponse, MarketDataIntradayResponse

router = APIRouter(prefix="/market-data", tags=["market-data"])


async def _get_stock_by_ticker(ticker: str, db: AsyncSession) -> Stock:
    result = await db.execute(select(Stock).where(func.upper(Stock.ticker) == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise NotFoundError(f"Stock {ticker} not found")
    return stock


@router.get("/{ticker}/daily", response_model=list[MarketDataDailyResponse])
async def get_daily_data(
    ticker: str,
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(365, ge=1, le=1000),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_by_ticker(ticker, db)

    query = select(MarketDataDaily).where(MarketDataDaily.stock_id == stock.id)

    if start_date:
        query = query.where(MarketDataDaily.date >= start_date)
    if end_date:
        query = query.where(MarketDataDaily.date <= end_date)

    query = query.order_by(MarketDataDaily.date.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    # Return in ascending date order for charting
    return [MarketDataDailyResponse.model_validate(row) for row in reversed(rows)]


@router.get("/{ticker}/intraday", response_model=list[MarketDataIntradayResponse])
async def get_intraday_data(
    ticker: str,
    limit: int = Query(100, ge=1, le=500),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_by_ticker(ticker, db)

    query = (
        select(MarketDataIntraday)
        .where(MarketDataIntraday.stock_id == stock.id)
        .order_by(MarketDataIntraday.timestamp.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.scalars().all()

    return [MarketDataIntradayResponse.model_validate(row) for row in reversed(rows)]
