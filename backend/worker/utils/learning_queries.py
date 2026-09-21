"""Shared DB loaders for the daily-view learning loop (optimizer + ML)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_signal_view import DailySignalView, DailySignalViewOutcome
from app.models.signal import Signal
from app.models.stock import Stock
from worker.utils.daily_aggregation import MIN_CONVICTION


async def fetch_learning_view_outcomes(
    session: AsyncSession,
    cutoff: datetime,
    sector_id: int | None = None,
    *,
    order_by_date: bool = False,
) -> list[tuple[DailySignalView, DailySignalViewOutcome]]:
    """1-day daily-view outcomes that meet the learning floor."""
    query = (
        select(DailySignalView, DailySignalViewOutcome)
        .join(DailySignalViewOutcome, DailySignalViewOutcome.daily_view_id == DailySignalView.id)
        .join(Stock, DailySignalView.stock_id == Stock.id)
        .where(DailySignalViewOutcome.window_days == 1)
        .where(DailySignalViewOutcome.evaluated_at >= cutoff)
        .where(DailySignalView.conviction >= MIN_CONVICTION)
        .where(DailySignalView.direction.in_(["bullish", "bearish"]))
    )
    if sector_id is not None:
        query = query.where(Stock.sector_id == sector_id)
    if order_by_date:
        query = query.order_by(DailySignalView.trading_date.asc())
    result = await session.execute(query)
    return list(result.all())


async def load_signals_for_views(
    session: AsyncSession, views: list[DailySignalView]
) -> dict[tuple[int, date], list[Signal]]:
    """Contributing signals keyed by (stock_id, trading_date)."""
    if not views:
        return {}
    stock_ids = {view.stock_id for view in views}
    dates = {view.trading_date for view in views}
    result = await session.execute(
        select(Signal)
        .where(Signal.stock_id.in_(stock_ids))
        .where(Signal.trading_date.in_(dates))
        .where(Signal.composite_score.isnot(None))
    )
    wanted = {(view.stock_id, view.trading_date) for view in views}
    grouped: dict[tuple[int, date], list[Signal]] = {}
    for signal in result.scalars().all():
        key = (signal.stock_id, signal.trading_date)
        if key not in wanted:
            continue
        grouped.setdefault(key, []).append(signal)
    return grouped
