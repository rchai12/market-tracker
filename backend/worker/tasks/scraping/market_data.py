"""Market data ingestion task using yfinance."""

import logging
import math
from datetime import date, datetime, timezone

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.market_data import MarketDataDaily
from app.models.stock import Stock
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _fetch_market_data_sync(tickers: list[str], period: str = "5d") -> dict:
    """Synchronous yfinance download (called from Celery worker)."""
    if not tickers:
        return {}

    data = yf.download(tickers, period=period, group_by="ticker", progress=False, threads=False)

    result = {}
    if len(tickers) == 1:
        # yfinance returns flat DataFrame for single ticker
        ticker = tickers[0]
        if not data.empty:
            result[ticker] = data
    else:
        for ticker in tickers:
            try:
                ticker_data = data[ticker]
                if not ticker_data.empty:
                    result[ticker] = ticker_data
            except (KeyError, TypeError):
                logger.warning(f"No data returned for {ticker}")
                continue

    return result


async def _get_active_tickers() -> dict[str, int]:
    """Get all active tickers and their stock IDs."""
    async with async_session() as session:
        result = await session.execute(
            select(Stock.ticker, Stock.id).where(Stock.is_active == True)  # noqa: E712
        )
        return {row.ticker: row.id for row in result.all()}


async def _store_daily_data(stock_id: int, ticker: str, df) -> int:
    """Upsert daily OHLCV data for a stock. Returns count of rows upserted."""
    if df is None or df.empty:
        return 0

    def _safe_float(val):
        if val is None:
            return None
        v = float(val)
        return None if math.isnan(v) or math.isinf(v) else v

    def _safe_int(val):
        if val is None:
            return None
        v = float(val)
        return None if math.isnan(v) or math.isinf(v) else int(v)

    rows = []
    for idx, row in df.iterrows():
        # idx is the date index from yfinance
        row_date = idx.date() if hasattr(idx, "date") else idx

        close = _safe_float(row.get("Close"))
        if close is None:
            continue

        rows.append({
            "stock_id": stock_id,
            "date": row_date,
            "open": _safe_float(row.get("Open")),
            "high": _safe_float(row.get("High")),
            "low": _safe_float(row.get("Low")),
            "close": close,
            "adj_close": _safe_float(row.get("Adj Close")),
            "volume": _safe_int(row.get("Volume")),
            "source": "yfinance",
        })

    if not rows:
        return 0

    async with async_session() as session:
        stmt = pg_insert(MarketDataDaily).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_market_data_daily_stock_date",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "adj_close": stmt.excluded.adj_close,
                "volume": stmt.excluded.volume,
                "source": stmt.excluded.source,
            },
        )
        await session.execute(stmt)
        await session.commit()

    return len(rows)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def fetch_all_market_data(self, period: str = "5d"):
    """Fetch daily OHLCV for all active tickers via yfinance batch API."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_fetch_all_market_data_async(period))
        return result
    except Exception as exc:
        logger.error(f"Market data fetch failed: {exc}")
        raise self.retry(exc=exc)


async def _fetch_all_market_data_async(period: str = "5d") -> dict:
    """Async wrapper for market data fetch + store."""
    ticker_map = await _get_active_tickers()
    tickers = list(ticker_map.keys())

    if not tickers:
        logger.warning("No active tickers found")
        return {"status": "no_tickers", "count": 0}

    logger.info(f"Fetching market data for {len(tickers)} tickers")

    # yfinance download is synchronous
    data = _fetch_market_data_sync(tickers, period)

    total_rows = 0
    errors = 0
    for ticker, df in data.items():
        try:
            stock_id = ticker_map.get(ticker)
            if stock_id is None:
                continue
            count = await _store_daily_data(stock_id, ticker, df)
            total_rows += count
        except Exception as e:
            logger.error(f"Failed to store data for {ticker}: {e}")
            errors += 1

    logger.info(f"Market data complete: {total_rows} rows stored, {errors} errors")
    return {"status": "complete", "rows": total_rows, "errors": errors}


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def seed_historical_market_data(self, period: str = "max"):
    """One-time task to backfill historical OHLCV data.

    Call manually: seed_historical_market_data.delay("max")
    Uses the same storage/upsert logic as the hourly task.
    """
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_fetch_all_market_data_async(period))
        return result
    except Exception as exc:
        logger.error(f"Historical market data seed failed: {exc}")
        raise self.retry(exc=exc)
