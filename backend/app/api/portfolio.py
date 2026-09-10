"""Paper portfolio API: summary, positions, trades, equity curve, stats."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db
from app.models.market_data import MarketDataDaily
from app.models.paper_portfolio import (
    PaperPortfolio,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperTrade,
)
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import PaginationMeta, PaginationParams, calc_total_pages, get_total_count
from app.schemas.portfolio import (
    PaginatedTrades,
    PortfolioPerformance,
    PortfolioPosition,
    PortfolioSnapshot,
    PortfolioStats,
    PortfolioSummary,
    PortfolioTrade,
)
from worker.utils.paper_portfolio import compute_portfolio_stats

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await _active_portfolio(db)
    positions = await _positions(db, portfolio.id)
    closes = await _latest_closes(db, [p.stock_id for p in positions])
    equity = sum(p.shares * closes.get(p.stock_id, p.entry_price) for p in positions)
    total_value = portfolio.current_cash + equity
    cash_pct = (portfolio.current_cash / total_value * 100.0) if total_value else 0.0
    total_return = (
        (total_value - portfolio.starting_capital) / portfolio.starting_capital * 100.0
        if portfolio.starting_capital
        else 0.0
    )
    bench_return = None
    if portfolio.benchmark_inception_price and portfolio.benchmark_inception_price > 0:
        spy_id = (
            await db.execute(select(Stock.id).where(Stock.ticker == portfolio.benchmark_ticker.upper()))
        ).scalar_one_or_none()
        spy_close = (await _latest_closes(db, [spy_id])).get(spy_id) if spy_id is not None else None
        if spy_close is not None:
            bench_return = (
                (spy_close - portfolio.benchmark_inception_price) / portfolio.benchmark_inception_price * 100.0
            )
    return PortfolioSummary(
        inception_date=portfolio.inception_date,
        starting_capital=portfolio.starting_capital,
        current_cash=round(portfolio.current_cash, 2),
        cash_pct=round(cash_pct, 2),
        total_value=round(total_value, 2),
        total_return_pct=round(total_return, 4),
        benchmark_return_pct=None if bench_return is None else round(bench_return, 4),
        open_positions=len(positions),
        benchmark_ticker=portfolio.benchmark_ticker,
    )


@router.get("/positions", response_model=list[PortfolioPosition])
async def get_portfolio_positions(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await _active_portfolio(db)
    positions = await _positions(db, portfolio.id)
    closes = await _latest_closes(db, [p.stock_id for p in positions])
    rows: list[PortfolioPosition] = []
    for pos in positions:
        stock = pos.stock
        current = closes.get(pos.stock_id)
        pnl = None
        pnl_pct = None
        if current is not None:
            pnl = pos.shares * (current - pos.entry_price)
            pnl_pct = ((current - pos.entry_price) / pos.entry_price * 100.0) if pos.entry_price else 0.0
        rows.append(
            PortfolioPosition(
                id=pos.id,
                stock_id=pos.stock_id,
                ticker=stock.ticker if stock else "???",
                company_name=stock.company_name if stock else "Unknown",
                sector=stock.sector.name if stock is not None and stock.sector is not None else None,
                opened_at=pos.opened_at,
                entry_price=pos.entry_price,
                current_price=current,
                shares=pos.shares,
                unrealized_pnl=None if pnl is None else round(pnl, 2),
                unrealized_pnl_pct=None if pnl_pct is None else round(pnl_pct, 4),
                stop_loss_price=pos.stop_loss_price,
                take_profit_price=pos.take_profit_price,
            )
        )
    return rows


@router.get("/trades", response_model=PaginatedTrades)
async def get_portfolio_trades(
    pagination: PaginationParams = Depends(),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await _active_portfolio(db)
    base = select(PaperTrade).where(PaperTrade.portfolio_id == portfolio.id)
    total = await get_total_count(db, base)
    result = await db.execute(
        base.options(joinedload(PaperTrade.stock))
        .order_by(PaperTrade.closed_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    trades = result.unique().scalars().all()
    return PaginatedTrades(
        data=[
            PortfolioTrade(
                id=t.id,
                ticker=t.stock.ticker if t.stock else "???",
                opened_at=t.opened_at,
                closed_at=t.closed_at,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                shares=t.shares,
                realized_pnl=t.realized_pnl,
                return_pct=t.return_pct,
                exit_reason=t.exit_reason,
            )
            for t in trades
        ],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )


@router.get("/performance", response_model=PortfolioPerformance)
async def get_portfolio_performance(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await _active_portfolio(db)
    result = await db.execute(
        select(PaperPortfolioSnapshot)
        .where(PaperPortfolioSnapshot.portfolio_id == portfolio.id)
        .order_by(PaperPortfolioSnapshot.snapshot_date.asc())
    )
    snaps = result.scalars().all()
    inception = portfolio.benchmark_inception_price
    points: list[PortfolioSnapshot] = []
    for snap in snaps:
        bench_value = None
        if snap.benchmark_price is not None and inception and inception > 0:
            bench_value = portfolio.starting_capital * (snap.benchmark_price / inception)
        points.append(
            PortfolioSnapshot(
                date=snap.snapshot_date,
                total_value=snap.total_value,
                benchmark_value=None if bench_value is None else round(bench_value, 2),
            )
        )
    return PortfolioPerformance(starting_capital=portfolio.starting_capital, points=points)


@router.get("/stats", response_model=PortfolioStats)
async def get_portfolio_stats(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await _active_portfolio(db)
    snap_result = await db.execute(
        select(PaperPortfolioSnapshot)
        .where(PaperPortfolioSnapshot.portfolio_id == portfolio.id)
        .order_by(PaperPortfolioSnapshot.snapshot_date.asc())
    )
    snaps = list(snap_result.scalars().all())
    trade_result = await db.execute(select(PaperTrade.return_pct).where(PaperTrade.portfolio_id == portfolio.id))
    trade_pcts = [float(r[0]) for r in trade_result.all()]

    total_values = [s.total_value for s in snaps]
    port_rets: list[float] = []
    bench_rets: list[float] = []
    for i in range(1, len(snaps)):
        prev, curr = snaps[i - 1], snaps[i]
        if prev.total_value > 0:
            port_rets.append((curr.total_value - prev.total_value) / prev.total_value)
        if prev.benchmark_price is not None and curr.benchmark_price is not None and prev.benchmark_price > 0:
            bench_rets.append((curr.benchmark_price - prev.benchmark_price) / prev.benchmark_price)

    stats = compute_portfolio_stats(total_values, port_rets, bench_rets, trade_pcts)
    return PortfolioStats(**stats)


async def _active_portfolio(db: AsyncSession) -> PaperPortfolio:
    result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.is_active.is_(True)).order_by(PaperPortfolio.id.asc()).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise NotFoundError("Paper portfolio has not been created yet")
    return portfolio


async def _positions(db: AsyncSession, portfolio_id: int) -> list[PaperPosition]:
    result = await db.execute(
        select(PaperPosition)
        .options(joinedload(PaperPosition.stock).joinedload(Stock.sector))
        .where(PaperPosition.portfolio_id == portfolio_id)
        .order_by(PaperPosition.opened_at.desc())
    )
    return list(result.unique().scalars().all())


async def _latest_closes(db: AsyncSession, stock_ids: list[int]) -> dict[int, float]:
    out: dict[int, float] = {}
    for stock_id in stock_ids:
        if stock_id is None:
            continue
        result = await db.execute(
            select(MarketDataDaily.close)
            .where(MarketDataDaily.stock_id == stock_id)
            .where(MarketDataDaily.close.isnot(None))
            .order_by(MarketDataDaily.date.desc())
            .limit(1)
        )
        val = result.scalar_one_or_none()
        if val is not None:
            out[stock_id] = float(val)
    return out
