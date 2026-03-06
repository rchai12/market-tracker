"""Seed historical market data for all active tickers.

Run once after initial setup to backfill the full available price history
so the signal algorithm has deep historical context from day one.

Usage:
    python -m scripts.seed_historical_data              # default: max history
    python -m scripts.seed_historical_data --period 10y
    python -m scripts.seed_historical_data --period 5y
"""

import argparse
import asyncio
import logging
import sys
import time

import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.market_data import MarketDataDaily
from app.models.stock import Stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# yfinance batch limit — download in chunks to avoid timeouts
BATCH_SIZE = 20


def download_batch(tickers: list[str], period: str) -> dict:
    """Download historical data for a batch of tickers."""
    if not tickers:
        return {}

    data = yf.download(
        tickers,
        period=period,
        group_by="ticker",
        progress=False,
        threads=False,
    )

    result = {}
    if len(tickers) == 1:
        ticker = tickers[0]
        if not data.empty:
            result[ticker] = data
    else:
        for ticker in tickers:
            try:
                ticker_data = data[ticker]
                if not ticker_data.empty and not ticker_data.isna().all().all():
                    result[ticker] = ticker_data
            except (KeyError, TypeError):
                continue

    return result


async def get_active_tickers() -> dict[str, int]:
    """Get all active tickers and their stock IDs."""
    async with async_session() as session:
        result = await session.execute(
            select(Stock.ticker, Stock.id).where(Stock.is_active == True)  # noqa: E712
        )
        return {row.ticker: row.id for row in result.all()}


async def get_existing_data_counts() -> dict[int, int]:
    """Get row counts per stock_id in market_data_daily."""
    async with async_session() as session:
        result = await session.execute(
            select(
                MarketDataDaily.stock_id,
                func.count(MarketDataDaily.id).label("cnt"),
            ).group_by(MarketDataDaily.stock_id)
        )
        return {row.stock_id: row.cnt for row in result.all()}


async def store_historical_data(stock_id: int, ticker: str, df) -> int:
    """Upsert historical daily OHLCV data. Returns count of rows upserted."""
    if df is None or df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        row_date = idx.date() if hasattr(idx, "date") else idx
        rows.append({
            "stock_id": stock_id,
            "date": row_date,
            "open": float(row.get("Open", 0)) if row.get("Open") is not None else None,
            "high": float(row.get("High", 0)) if row.get("High") is not None else None,
            "low": float(row.get("Low", 0)) if row.get("Low") is not None else None,
            "close": float(row.get("Close", 0)) if row.get("Close") is not None else None,
            "adj_close": float(row.get("Adj Close", 0)) if row.get("Adj Close") is not None else None,
            "volume": int(row.get("Volume", 0)) if row.get("Volume") is not None else None,
            "source": "yfinance",
        })

    if not rows:
        return 0

    async with async_session() as session:
        # Insert in chunks of 500 to avoid huge queries
        for i in range(0, len(rows), 500):
            chunk = rows[i : i + 500]
            stmt = pg_insert(MarketDataDaily).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_market_data_daily_stock_id",
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


async def seed_historical(period: str = "max", skip_existing: bool = True):
    """Main entry point: download and store historical data for all active tickers."""
    ticker_map = await get_active_tickers()
    if not ticker_map:
        logger.error("No active tickers found. Run seed_sp500.py first.")
        return

    existing_counts = await get_existing_data_counts() if skip_existing else {}

    # Filter out tickers that already have substantial historical data
    # 5000 rows ≈ ~20 years of trading days, good enough to skip re-download
    tickers_to_fetch = []
    for ticker, stock_id in ticker_map.items():
        count = existing_counts.get(stock_id, 0)
        if skip_existing and count >= 5000:
            logger.info(f"  Skipping {ticker} — already has {count} rows")
            continue
        tickers_to_fetch.append(ticker)

    if not tickers_to_fetch:
        logger.info("All tickers already have historical data. Nothing to do.")
        return

    logger.info(f"Seeding {period} of historical data for {len(tickers_to_fetch)} tickers")

    total_rows = 0
    errors = 0

    # Process in batches
    for i in range(0, len(tickers_to_fetch), BATCH_SIZE):
        batch = tickers_to_fetch[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(tickers_to_fetch) + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"  Batch {batch_num}/{total_batches}: {', '.join(batch)}")

        try:
            data = download_batch(batch, period)

            for ticker, df in data.items():
                stock_id = ticker_map.get(ticker)
                if stock_id is None:
                    continue
                try:
                    count = await store_historical_data(stock_id, ticker, df)
                    total_rows += count
                    logger.info(f"    {ticker}: {count} rows")
                except Exception as e:
                    logger.error(f"    {ticker}: failed to store — {e}")
                    errors += 1

        except Exception as e:
            logger.error(f"  Batch download failed: {e}")
            errors += len(batch)

        # Be polite to yfinance servers between batches
        if i + BATCH_SIZE < len(tickers_to_fetch):
            time.sleep(2)

    logger.info(f"Historical seed complete: {total_rows} total rows, {errors} errors")


def main():
    parser = argparse.ArgumentParser(description="Seed historical market data")
    parser.add_argument(
        "--period",
        default="max",
        choices=["1y", "2y", "5y", "10y", "max"],
        help="How far back to fetch (default: max — full available history)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if data already exists",
    )
    args = parser.parse_args()

    asyncio.run(seed_historical(period=args.period, skip_existing=not args.force))


if __name__ == "__main__":
    main()
