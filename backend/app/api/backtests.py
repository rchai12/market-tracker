"""Backtest API endpoints."""

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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


def _float_or_none(v) -> float | None:
    return float(v) if v is not None else None


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
        commission_pct=body.commission_pct,
        slippage_pct=body.slippage_pct,
        position_size_pct=body.position_size_pct,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
        benchmark_ticker=body.benchmark_ticker,
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
    equity_curve = _parse_equity_curve(bt.equity_curve)

    # Parse benchmark equity curve JSON
    benchmark_equity_curve = _parse_equity_curve(bt.benchmark_equity_curve)

    # Sort trades by date
    trades = sorted(bt.trades, key=lambda t: t.trade_date)

    ticker = bt.stock.ticker if bt.stock else None
    sector_name = bt.sector.name if bt.sector else None

    resp = _to_response(bt, ticker=ticker, sector_name=sector_name)
    return BacktestDetailResponse(
        **resp.model_dump(),
        equity_curve=equity_curve,
        trades=[BacktestTradeResponse.model_validate(t) for t in trades],
        benchmark_equity_curve=benchmark_equity_curve if benchmark_equity_curve else None,
    )


@router.get("/{backtest_id}/export")
async def export_backtest(
    backtest_id: int,
    type: str = Query(..., pattern="^(trades|equity_curve)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export backtest data as CSV."""
    result = await db.execute(
        select(Backtest)
        .where(Backtest.id == backtest_id)
        .where(Backtest.user_id == user.id)
        .options(joinedload(Backtest.trades))
    )
    bt = result.unique().scalar_one_or_none()

    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")
    if bt.status != "completed":
        raise HTTPException(status_code=400, detail="Backtest is not completed")

    output = io.StringIO()
    writer = csv.writer(output)

    if type == "trades":
        writer.writerow([
            "Date", "Ticker", "Action", "Price", "Shares",
            "Position Value", "Portfolio Equity", "Signal Score",
            "Signal Direction", "Signal Strength", "Return %", "Exit Reason",
        ])
        for trade in sorted(bt.trades, key=lambda t: t.trade_date):
            writer.writerow([
                trade.trade_date.strftime("%Y-%m-%d"),
                trade.ticker, trade.action,
                f"{float(trade.price):.4f}",
                f"{float(trade.shares):.6f}",
                f"{float(trade.position_value):.2f}",
                f"{float(trade.portfolio_equity):.2f}",
                f"{float(trade.signal_score):.5f}",
                trade.signal_direction, trade.signal_strength,
                f"{float(trade.return_pct):.4f}" if trade.return_pct is not None else "",
                trade.exit_reason or "",
            ])
        filename = f"backtest_{backtest_id}_trades.csv"
    else:
        writer.writerow(["Date", "Equity"])
        if bt.equity_curve:
            try:
                for point in json.loads(bt.equity_curve):
                    writer.writerow([point["date"], f"{point['equity']:.2f}"])
            except (json.JSONDecodeError, TypeError):
                pass
        filename = f"backtest_{backtest_id}_equity_curve.csv"

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
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


def _parse_equity_curve(raw: str | None) -> list[EquityPointResponse]:
    if not raw:
        return []
    try:
        return [EquityPointResponse(**p) for p in json.loads(raw)]
    except (json.JSONDecodeError, TypeError):
        return []


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
        commission_pct=_float_or_none(bt.commission_pct),
        slippage_pct=_float_or_none(bt.slippage_pct),
        position_size_pct=_float_or_none(bt.position_size_pct),
        stop_loss_pct=_float_or_none(bt.stop_loss_pct),
        take_profit_pct=_float_or_none(bt.take_profit_pct),
        benchmark_ticker=bt.benchmark_ticker,
        total_return_pct=_float_or_none(bt.total_return_pct),
        annualized_return_pct=_float_or_none(bt.annualized_return_pct),
        sharpe_ratio=_float_or_none(bt.sharpe_ratio),
        max_drawdown_pct=_float_or_none(bt.max_drawdown_pct),
        win_rate_pct=_float_or_none(bt.win_rate_pct),
        total_trades=bt.total_trades,
        avg_win_pct=_float_or_none(bt.avg_win_pct),
        avg_loss_pct=_float_or_none(bt.avg_loss_pct),
        best_trade_pct=_float_or_none(bt.best_trade_pct),
        worst_trade_pct=_float_or_none(bt.worst_trade_pct),
        final_equity=_float_or_none(bt.final_equity),
        benchmark_total_return_pct=_float_or_none(bt.benchmark_total_return_pct),
        benchmark_annualized_return_pct=_float_or_none(bt.benchmark_annualized_return_pct),
        alpha=_float_or_none(bt.alpha),
        beta=_float_or_none(bt.beta),
        error_message=bt.error_message,
        created_at=bt.created_at,
        completed_at=bt.completed_at,
    )
