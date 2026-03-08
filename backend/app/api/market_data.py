from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cached
from app.dependencies import get_current_user, get_db, get_stock_by_ticker
from app.models.cboe_put_call import CboePutCallRatio
from app.models.market_data import MarketDataDaily, MarketDataIntraday
from app.models.options_activity import OptionsActivity
from app.models.user import User
from app.schemas.market_data import IndicatorDataResponse, MarketDataDailyResponse, MarketDataIntradayResponse
from app.schemas.options import CboePutCallResponse, OptionsActivityResponse

router = APIRouter(prefix="/market-data", tags=["market-data"])


# Static paths MUST come before {ticker} parameterized routes
@router.get("/cboe/put-call-ratio", response_model=list[CboePutCallResponse])
async def get_cboe_put_call_ratio(
    days: int = Query(90, ge=1, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get market-wide CBOE put/call ratio history."""
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(CboePutCallRatio)
        .where(CboePutCallRatio.date >= since)
        .order_by(CboePutCallRatio.date.asc())
    )
    rows = result.scalars().all()
    return [CboePutCallResponse.model_validate(row) for row in rows]


@router.get("/{ticker}/daily", response_model=list[MarketDataDailyResponse])
async def get_daily_data(
    ticker: str,
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(365, ge=1, le=1000),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stock = await get_stock_by_ticker(ticker, db)

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


@router.get("/{ticker}/indicators", response_model=list[IndicatorDataResponse])
@cached("market-data:indicators", ttl=3600)
async def get_indicators(
    ticker: str,
    days: int = Query(365, ge=30, le=1000),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute and return technical indicators for charting."""
    from worker.utils.technical_indicators import (
        compute_bollinger_bands,
        compute_macd,
        compute_rsi,
        compute_sma,
    )

    stock = await get_stock_by_ticker(ticker, db)

    # Fetch extra rows for indicator warmup (SMA50 needs 50, MACD needs ~35)
    warmup = 60
    query = (
        select(MarketDataDaily)
        .where(MarketDataDaily.stock_id == stock.id)
        .where(MarketDataDaily.close != None)  # noqa: E711
        .order_by(MarketDataDaily.date.desc())
        .limit(days + warmup)
    )
    result = await db.execute(query)
    rows = list(reversed(result.scalars().all()))

    if len(rows) < 30:
        return []

    closes = [float(r.close) for r in rows]
    dates = [r.date for r in rows]

    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    rsi = compute_rsi(closes, 14)
    macd = compute_macd(closes)
    bb = compute_bollinger_bands(closes)

    # Only return the last `days` entries (trim warmup)
    start_idx = max(0, len(rows) - days)
    results = []
    for i in range(start_idx, len(rows)):
        results.append(
            IndicatorDataResponse(
                date=dates[i],
                sma20=round(sma20[i], 4) if sma20[i] is not None else None,
                sma50=round(sma50[i], 4) if sma50[i] is not None else None,
                rsi=round(rsi[i], 2) if rsi[i] is not None else None,
                macd_line=round(macd[i]["macd_line"], 4) if macd[i]["macd_line"] is not None else None,
                macd_signal=round(macd[i]["signal_line"], 4) if macd[i]["signal_line"] is not None else None,
                macd_histogram=round(macd[i]["histogram"], 4) if macd[i]["histogram"] is not None else None,
                bb_upper=round(bb[i]["upper"], 4) if bb[i]["upper"] is not None else None,
                bb_middle=round(bb[i]["middle"], 4) if bb[i]["middle"] is not None else None,
                bb_lower=round(bb[i]["lower"], 4) if bb[i]["lower"] is not None else None,
            )
        )

    return results


@router.get("/{ticker}/intraday", response_model=list[MarketDataIntradayResponse])
async def get_intraday_data(
    ticker: str,
    limit: int = Query(100, ge=1, le=500),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stock = await get_stock_by_ticker(ticker, db)

    query = (
        select(MarketDataIntraday)
        .where(MarketDataIntraday.stock_id == stock.id)
        .order_by(MarketDataIntraday.timestamp.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.scalars().all()

    return [MarketDataIntradayResponse.model_validate(row) for row in reversed(rows)]


@router.get("/{ticker}/options", response_model=list[OptionsActivityResponse])
async def get_options_activity(
    ticker: str,
    days: int = Query(30, ge=1, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get options activity history for a ticker."""
    stock = await get_stock_by_ticker(ticker, db)

    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(OptionsActivity)
        .where(OptionsActivity.stock_id == stock.id)
        .where(OptionsActivity.date >= since)
        .order_by(OptionsActivity.date.asc())
    )
    rows = result.scalars().all()
    return [OptionsActivityResponse.model_validate(row) for row in rows]
