"""Paper portfolio Celery tasks: open/close positions and daily snapshots."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import async_session
from app.models.paper_portfolio import (
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
)
from app.models.signal import Signal
from app.models.stock import Stock
from worker.utils.celery_helpers import async_task
from worker.utils.market_data_queries import latest_close, latest_closes
from worker.utils.paper_portfolio import (
    OpenCandidate,
    close_reason,
    decide_opens,
    is_weekday,
    snapshot_returns,
)

logger = logging.getLogger(__name__)


@async_task("worker.tasks.signals.paper_portfolio_task.update_paper_portfolio")
async def update_paper_portfolio() -> dict:
    """Close/open paper positions from latest signals. Beat: :35 weekdays."""
    if not settings.paper_portfolio_enabled:
        return {"skipped": True, "reason": "disabled"}
    now = datetime.now(UTC)
    if not is_weekday(now.weekday()):
        return {"skipped": True, "reason": "weekend"}
    async with async_session() as session:
        result = await _update_portfolio(session, now)
        await session.commit()
    return result


@async_task("worker.tasks.signals.paper_portfolio_task.snapshot_paper_portfolio")
async def snapshot_paper_portfolio() -> dict:
    """Record daily equity vs SPY. Beat: 21:30 UTC."""
    if not settings.paper_portfolio_enabled:
        return {"skipped": True, "reason": "disabled"}
    now = datetime.now(UTC)
    async with async_session() as session:
        result = await _snapshot_portfolio(session, now)
        await session.commit()
    return result


async def _update_portfolio(session: AsyncSession, now: datetime) -> dict:
    portfolio = await _get_or_create_portfolio(session, now)
    positions = await _load_positions(session, portfolio.id)
    closes = await _close_positions(session, portfolio, positions, now)
    remaining = await _load_positions(session, portfolio.id)
    opens = await _open_positions(session, portfolio, remaining, now)
    logger.info(
        "Paper portfolio update: opened=%s closed=%s pnl=%.2f cash=%.2f",
        opens,
        len(closes),
        sum(c["realized_pnl"] for c in closes),
        portfolio.current_cash,
    )
    return {
        "opened": opens,
        "closed": len(closes),
        "realized_pnl": round(sum(c["realized_pnl"] for c in closes), 2),
        "cash": round(portfolio.current_cash, 2),
    }


async def _snapshot_portfolio(session: AsyncSession, now: datetime) -> dict:
    portfolio = await _get_or_create_portfolio(session, now)
    positions = await _load_positions(session, portfolio.id)
    closes = await latest_closes(session, [p.stock_id for p in positions])
    equity = 0.0
    for pos in positions:
        price = closes.get(pos.stock_id)
        if price is None:
            price = pos.entry_price
        equity += pos.shares * price
    total_value = portfolio.current_cash + equity
    spy_id = await _stock_id_by_ticker(session, portfolio.benchmark_ticker)
    spy_close = await latest_close(session, spy_id) if spy_id is not None else None

    prev = await session.execute(
        select(PaperPortfolioSnapshot)
        .where(PaperPortfolioSnapshot.portfolio_id == portfolio.id)
        .where(PaperPortfolioSnapshot.snapshot_date < now.date())
        .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
        .limit(1)
    )
    previous = prev.scalar_one_or_none()
    prev_total = previous.total_value if previous is not None else None

    metrics = snapshot_returns(
        total_value,
        portfolio.starting_capital,
        prev_total,
        spy_close,
        portfolio.benchmark_inception_price,
    )
    stmt = (
        pg_insert(PaperPortfolioSnapshot)
        .values(
            portfolio_id=portfolio.id,
            snapshot_date=now.date(),
            total_value=total_value,
            cash=portfolio.current_cash,
            equity_value=equity,
            open_positions=len(positions),
            benchmark_price=spy_close,
            daily_return_pct=metrics["daily_return_pct"],
            cumulative_return_pct=metrics["cumulative_return_pct"],
            benchmark_cumulative_return_pct=metrics["benchmark_cumulative_return_pct"],
        )
        .on_conflict_do_update(
            constraint="uq_paper_snapshot_date",
            set_={
                "total_value": total_value,
                "cash": portfolio.current_cash,
                "equity_value": equity,
                "open_positions": len(positions),
                "benchmark_price": spy_close,
                "daily_return_pct": metrics["daily_return_pct"],
                "cumulative_return_pct": metrics["cumulative_return_pct"],
                "benchmark_cumulative_return_pct": metrics["benchmark_cumulative_return_pct"],
            },
        )
    )
    await session.execute(stmt)
    logger.info(
        "Paper portfolio snapshot: total=%.2f equity=%.2f cash=%.2f positions=%s",
        total_value,
        equity,
        portfolio.current_cash,
        len(positions),
    )
    return {
        "total_value": round(total_value, 2),
        "equity_value": round(equity, 2),
        "cash": round(portfolio.current_cash, 2),
        "open_positions": len(positions),
        "cumulative_return_pct": metrics["cumulative_return_pct"],
    }


async def _get_or_create_portfolio(session: AsyncSession, now: datetime) -> PaperPortfolio:
    result = await session.execute(
        select(PaperPortfolio).where(PaperPortfolio.is_active.is_(True)).order_by(PaperPortfolio.id.asc()).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    spy_id = await _stock_id_by_ticker(session, "SPY")
    spy_close = await latest_close(session, spy_id) if spy_id is not None else None
    capital = settings.paper_portfolio_starting_capital
    portfolio = PaperPortfolio(
        inception_date=now.date(),
        starting_capital=capital,
        current_cash=capital,
        is_active=True,
        benchmark_ticker="SPY",
        benchmark_inception_price=spy_close,
    )
    session.add(portfolio)
    await session.flush()
    logger.info("Created paper portfolio id=%s capital=%.2f", portfolio.id, capital)
    return portfolio


async def _load_positions(session: AsyncSession, portfolio_id: int) -> list[PaperPosition]:
    result = await session.execute(
        select(PaperPosition).options(joinedload(PaperPosition.stock)).where(PaperPosition.portfolio_id == portfolio_id)
    )
    return list(result.unique().scalars().all())


async def _close_positions(
    session: AsyncSession,
    portfolio: PaperPortfolio,
    positions: list[PaperPosition],
    now: datetime,
) -> list[dict]:
    closed: list[dict] = []
    for pos in positions:
        price = await latest_close(session, pos.stock_id)
        if price is None:
            continue
        signal = await _latest_signal(session, pos.stock_id)
        direction = signal.direction if signal is not None else None
        reason = close_reason(
            pos.entry_price,
            price,
            direction,
            settings.paper_portfolio_stop_loss_pct,
            settings.paper_portfolio_take_profit_pct,
        )
        if reason is None:
            continue
        pnl = pos.shares * (price - pos.entry_price)
        ret_pct = ((price - pos.entry_price) / pos.entry_price) * 100.0 if pos.entry_price else 0.0
        trade = PaperTrade(
            portfolio_id=portfolio.id,
            stock_id=pos.stock_id,
            entry_signal_id=pos.entry_signal_id,
            exit_signal_id=signal.id if signal is not None and reason == "signal_reversal" else None,
            opened_at=pos.opened_at,
            closed_at=now,
            entry_price=pos.entry_price,
            exit_price=price,
            shares=pos.shares,
            realized_pnl=pnl,
            return_pct=ret_pct,
            exit_reason=reason,
        )
        session.add(trade)
        portfolio.current_cash += pos.shares * price
        await session.delete(pos)
        closed.append({"stock_id": pos.stock_id, "reason": reason, "realized_pnl": pnl})
    await session.flush()
    return closed


async def _open_positions(
    session: AsyncSession,
    portfolio: PaperPortfolio,
    positions: list[PaperPosition],
    now: datetime,
) -> int:
    closes = await latest_closes(session, [p.stock_id for p in positions])
    equity = sum(p.shares * closes.get(p.stock_id, p.entry_price) for p in positions)
    portfolio_value = portfolio.current_cash + equity
    sector_counts: dict[int | None, int] = {}
    for pos in positions:
        sid = pos.stock.sector_id if pos.stock is not None else None
        sector_counts[sid] = sector_counts.get(sid, 0) + 1

    candidates = await _open_candidates(session, {p.stock_id for p in positions})
    decisions = decide_opens(
        candidates,
        open_stock_ids={p.stock_id for p in positions},
        sector_counts=sector_counts,
        cash=portfolio.current_cash,
        portfolio_value=portfolio_value,
        max_positions=settings.paper_portfolio_max_positions,
        max_per_sector=settings.paper_portfolio_max_per_sector,
        position_size_pct=settings.paper_portfolio_position_size_pct,
        min_strength=settings.paper_portfolio_min_strength,
        stop_loss_pct=settings.paper_portfolio_stop_loss_pct,
        take_profit_pct=settings.paper_portfolio_take_profit_pct,
    )
    for decision in decisions:
        session.add(
            PaperPosition(
                portfolio_id=portfolio.id,
                stock_id=decision.stock_id,
                entry_signal_id=decision.signal_id,
                opened_at=now,
                entry_price=decision.entry_price,
                shares=float(decision.shares),
                stop_loss_price=decision.stop_loss_price,
                take_profit_price=decision.take_profit_price,
            )
        )
        portfolio.current_cash -= decision.cost
    await session.flush()
    return len(decisions)


async def _open_candidates(session: AsyncSession, held: set[int]) -> list[OpenCandidate]:
    latest_at = (
        select(Signal.stock_id, func.max(Signal.generated_at).label("max_at")).group_by(Signal.stock_id).subquery()
    )
    result = await session.execute(
        select(Signal)
        .join(
            latest_at,
            (Signal.stock_id == latest_at.c.stock_id) & (Signal.generated_at == latest_at.c.max_at),
        )
        .options(joinedload(Signal.stock))
        .where(Signal.direction == "bullish")
    )
    candidates: list[OpenCandidate] = []
    seen: set[int] = set()
    for signal in result.unique().scalars().all():
        if signal.stock_id in held or signal.stock_id in seen:
            continue
        seen.add(signal.stock_id)
        close = await latest_close(session, signal.stock_id)
        if close is None:
            continue
        stock = signal.stock
        candidates.append(
            OpenCandidate(
                stock_id=signal.stock_id,
                sector_id=stock.sector_id if stock is not None else None,
                signal_id=signal.id,
                strength=signal.strength,
                close_price=close,
                composite_score=float(signal.composite_score),
            )
        )
    return candidates


async def _latest_signal(session: AsyncSession, stock_id: int) -> Signal | None:
    result = await session.execute(
        select(Signal).where(Signal.stock_id == stock_id).order_by(Signal.generated_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _stock_id_by_ticker(session: AsyncSession, ticker: str) -> int | None:
    result = await session.execute(select(Stock.id).where(Stock.ticker == ticker.upper()))
    return result.scalar_one_or_none()
