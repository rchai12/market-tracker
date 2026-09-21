"""Shared daily OHLCV lookups (Postgres).

Outcome evaluation, paper portfolio, the portfolio API, and component
scorers must not each re-implement close-on-or-before / latest close.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import MarketDataDaily


async def close_on_or_before(session: AsyncSession, stock_id: int, target_date: date) -> float | None:
    """Close on *target_date*, or the most recent session before it."""
    result = await session.execute(
        select(MarketDataDaily.close)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.date <= target_date)
        .where(MarketDataDaily.close.isnot(None))
        .order_by(MarketDataDaily.date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return float(row) if row is not None else None


async def nth_trading_day_close(session: AsyncSession, stock_id: int, start_date: date, n: int) -> float | None:
    """Close *n* trading sessions after *start_date* (weekends/holidays skipped)."""
    result = await session.execute(
        select(MarketDataDaily.close)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.date > start_date)
        .where(MarketDataDaily.close.isnot(None))
        .order_by(MarketDataDaily.date.asc())
        .offset(n - 1)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return float(row) if row is not None else None


async def latest_closes(session: AsyncSession, stock_ids: list[int | None]) -> dict[int, float]:
    """Latest non-null close per stock in one DISTINCT ON query."""
    ids = list({sid for sid in stock_ids if sid is not None})
    if not ids:
        return {}
    result = await session.execute(
        select(MarketDataDaily.stock_id, MarketDataDaily.close)
        .where(MarketDataDaily.stock_id.in_(ids))
        .where(MarketDataDaily.close.isnot(None))
        .distinct(MarketDataDaily.stock_id)
        .order_by(MarketDataDaily.stock_id.asc(), MarketDataDaily.date.desc())
    )
    out: dict[int, float] = {}
    for stock_id, close in result.all():
        out[int(stock_id)] = float(close)
    return out


async def latest_close(session: AsyncSession, stock_id: int | None) -> float | None:
    if stock_id is None:
        return None
    return (await latest_closes(session, [stock_id])).get(stock_id)


async def recent_closes(session: AsyncSession, stock_id: int, limit: int) -> list[float]:
    """Most recent *limit* closes, oldest first."""
    result = await session.execute(
        select(MarketDataDaily.close)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.close.isnot(None))
        .order_by(MarketDataDaily.date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [float(close) for close in reversed(rows)]


async def recent_close_volume(session: AsyncSession, stock_id: int, limit: int) -> tuple[list[float], list[float]]:
    """Most recent *limit* (close, volume) pairs, oldest first. Rows need volume."""
    result = await session.execute(
        select(MarketDataDaily.close, MarketDataDaily.volume)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.volume.isnot(None))
        .order_by(MarketDataDaily.date.desc())
        .limit(limit)
    )
    rows = list(reversed(result.all()))
    closes = [float(row.close) if row.close is not None else 0.0 for row in rows]
    volumes = [float(row.volume) if row.volume is not None else 0.0 for row in rows]
    return closes, volumes
