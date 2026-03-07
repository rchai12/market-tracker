"""Backtest API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_current_user, get_db
from app.models.backtest import Backtest, BacktestTrade
from app.models.sector import Sector
from app.models.stock import Stock
from app.models.user import User
from app.schemas.backtest import (
    BacktestCreate,
    BacktestDetailResponse,
    BacktestResponse,
    BacktestTradeResponse,
    EquityPointResponse,
    PaginatedBacktests,
)
from app.schemas.common import PaginationMeta, calc_total_pages, get_total_count

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=BacktestResponse, status_code=201)
async def create_backtest(
    body: BacktestCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create and queue a new backtest."""
    stock_id = None
    sector_id = None
    ticker = None
    sector_name = None

    if body.ticker:
        result = await db.execute(
            select(Stock).where(Stock.ticker == body.ticker.upper())
        )
        stock = result.scalar_one_or_none()
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock '{body.ticker}' not found")
        stock_id = stock.id
        ticker = stock.ticker
    elif body.sector_name:
        result = await db.execute(
            select(Sector).where(Sector.name == body.sector_name)
        )
        sector = result.scalar_one_or_none()
        if not sector:
            raise HTTPException(status_code=404, detail=f"Sector '{body.sector_name}' not found")
        sector_id = sector.id
        sector_name = sector.name

    bt = Backtest(
        user_id=user.id,
        stock_id=stock_id,
        sector_id=sector_id,
        mode=body.mode,
        status="pending",
        start_date=body.start_date,
        end_date=body.end_date,
        starting_capital=body.starting_capital,
        min_signal_strength=body.min_signal_strength,
    )
    db.add(bt)
    await db.commit()
    await db.refresh(bt)

    # Queue Celery task
    from worker.tasks.signals.backtest_task import run_backtest_task

    run_backtest_task.delay(bt.id)

    return _to_response(bt, ticker=ticker, sector_name=sector_name)


@router.get("", response_model=PaginatedBacktests)
async def list_backtests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's backtests."""
    query = (
        select(Backtest)
        .where(Backtest.user_id == user.id)
        .order_by(Backtest.created_at.desc())
    )

    if status:
        query = query.where(Backtest.status == status)

    total = await get_total_count(db, query)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query.options(joinedload(Backtest.stock), joinedload(Backtest.sector)))
    backtests = result.unique().scalars().all()

    return PaginatedBacktests(
        data=[_to_response(bt) for bt in backtests],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=calc_total_pages(total, per_page),
        ),
    )


@router.get("/{backtest_id}", response_model=BacktestDetailResponse)
async def get_backtest(
    backtest_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get backtest detail with equity curve and trades."""
    result = await db.execute(
        select(Backtest)
        .where(Backtest.id == backtest_id)
        .where(Backtest.user_id == user.id)
        .options(joinedload(Backtest.stock), joinedload(Backtest.sector), joinedload(Backtest.trades))
    )
    bt = result.unique().scalar_one_or_none()

    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Parse equity curve JSON
    equity_curve = []
    if bt.equity_curve:
        try:
            equity_curve = [EquityPointResponse(**p) for p in json.loads(bt.equity_curve)]
        except (json.JSONDecodeError, TypeError):
            equity_curve = []

    # Sort trades by date
    trades = sorted(bt.trades, key=lambda t: t.trade_date)

    ticker = bt.stock.ticker if bt.stock else None
    sector_name = bt.sector.name if bt.sector else None

    return BacktestDetailResponse(
        id=bt.id,
        ticker=ticker,
        sector_name=sector_name,
        mode=bt.mode,
        status=bt.status,
        start_date=bt.start_date,
        end_date=bt.end_date,
        starting_capital=float(bt.starting_capital),
        min_signal_strength=bt.min_signal_strength,
        total_return_pct=float(bt.total_return_pct) if bt.total_return_pct is not None else None,
        annualized_return_pct=float(bt.annualized_return_pct) if bt.annualized_return_pct is not None else None,
        sharpe_ratio=float(bt.sharpe_ratio) if bt.sharpe_ratio is not None else None,
        max_drawdown_pct=float(bt.max_drawdown_pct) if bt.max_drawdown_pct is not None else None,
        win_rate_pct=float(bt.win_rate_pct) if bt.win_rate_pct is not None else None,
        total_trades=bt.total_trades,
        avg_win_pct=float(bt.avg_win_pct) if bt.avg_win_pct is not None else None,
        avg_loss_pct=float(bt.avg_loss_pct) if bt.avg_loss_pct is not None else None,
        best_trade_pct=float(bt.best_trade_pct) if bt.best_trade_pct is not None else None,
        worst_trade_pct=float(bt.worst_trade_pct) if bt.worst_trade_pct is not None else None,
        final_equity=float(bt.final_equity) if bt.final_equity is not None else None,
        error_message=bt.error_message,
        created_at=bt.created_at,
        completed_at=bt.completed_at,
        equity_curve=equity_curve,
        trades=[BacktestTradeResponse.model_validate(t) for t in trades],
    )


@router.delete("/{backtest_id}", status_code=204)
async def delete_backtest(
    backtest_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a backtest (cascade deletes trades)."""
    result = await db.execute(
        select(Backtest)
        .where(Backtest.id == backtest_id)
        .where(Backtest.user_id == user.id)
    )
    bt = result.scalar_one_or_none()

    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")

    await db.delete(bt)
    await db.commit()


def _to_response(bt: Backtest, ticker: str | None = None, sector_name: str | None = None) -> BacktestResponse:
    """Convert a Backtest ORM object to a BacktestResponse."""
    if ticker is None and bt.stock:
        ticker = bt.stock.ticker
    if sector_name is None and bt.sector:
        sector_name = bt.sector.name

    return BacktestResponse(
        id=bt.id,
        ticker=ticker,
        sector_name=sector_name,
        mode=bt.mode,
        status=bt.status,
        start_date=bt.start_date,
        end_date=bt.end_date,
        starting_capital=float(bt.starting_capital),
        min_signal_strength=bt.min_signal_strength,
        total_return_pct=float(bt.total_return_pct) if bt.total_return_pct is not None else None,
        annualized_return_pct=float(bt.annualized_return_pct) if bt.annualized_return_pct is not None else None,
        sharpe_ratio=float(bt.sharpe_ratio) if bt.sharpe_ratio is not None else None,
        max_drawdown_pct=float(bt.max_drawdown_pct) if bt.max_drawdown_pct is not None else None,
        win_rate_pct=float(bt.win_rate_pct) if bt.win_rate_pct is not None else None,
        total_trades=bt.total_trades,
        avg_win_pct=float(bt.avg_win_pct) if bt.avg_win_pct is not None else None,
        avg_loss_pct=float(bt.avg_loss_pct) if bt.avg_loss_pct is not None else None,
        best_trade_pct=float(bt.best_trade_pct) if bt.best_trade_pct is not None else None,
        worst_trade_pct=float(bt.worst_trade_pct) if bt.worst_trade_pct is not None else None,
        final_equity=float(bt.final_equity) if bt.final_equity is not None else None,
        error_message=bt.error_message,
        created_at=bt.created_at,
        completed_at=bt.completed_at,
    )
