"""Celery task for running backtests.

Fetches OHLCV (and optionally sentiment) data from the database,
calls the pure backtesting engine, and stores results.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.backtest import Backtest, BacktestTrade
from app.models.market_data import MarketDataDaily
from app.models.sentiment import SentimentScore
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async
from worker.utils.backtester import (
    BacktestConfig,
    BacktestResult,
    BenchmarkResult,
    OHLCVRow,
    SentimentRow,
    aggregate_backtest_results,
    compute_benchmark,
    run_backtest,
)

logger = logging.getLogger(__name__)

WARMUP_BUFFER_DAYS = 90  # Extra days before start_date for indicator warmup


@celery_app.task(
    name="worker.tasks.signals.backtest_task.run_backtest_task",
    bind=True,
    max_retries=0,
)
def run_backtest_task(self, backtest_id: int):
    """Run a backtest. Called asynchronously after POST /api/backtests."""
    try:
        return run_async(_run_backtest_async(backtest_id, self.request.id))
    except Exception as exc:
        logger.error(f"Backtest {backtest_id} failed: {exc}")
        # Mark as failed in DB
        try:
            run_async(_mark_failed(backtest_id, str(exc)))
        except Exception:
            logger.error(f"Could not mark backtest {backtest_id} as failed")
        raise


async def _run_backtest_async(backtest_id: int, celery_task_id: str | None) -> dict:
    """Fetch data, run backtest engine, store results."""
    async with async_session() as session:
        # Load backtest record
        bt = await session.get(Backtest, backtest_id)
        if bt is None:
            raise ValueError(f"Backtest {backtest_id} not found")

        # Mark as running
        bt.status = "running"
        bt.celery_task_id = celery_task_id
        await session.commit()

        try:
            # Determine tickers
            if bt.stock_id:
                stock = await session.get(Stock, bt.stock_id)
                if not stock:
                    raise ValueError(f"Stock {bt.stock_id} not found")
                tickers = [(stock.ticker, stock.id)]
            elif bt.sector_id:
                result = await session.execute(
                    select(Stock.ticker, Stock.id)
                    .where(Stock.sector_id == bt.sector_id)
                    .where(Stock.is_active == True)  # noqa: E712
                )
                tickers = [(row.ticker, row.id) for row in result.all()]
                if not tickers:
                    raise ValueError(f"No active stocks in sector {bt.sector_id}")
            else:
                raise ValueError("Backtest must have stock_id or sector_id")

            per_ticker_capital = float(bt.starting_capital) / len(tickers) if len(tickers) > 1 else float(bt.starting_capital)

            config = BacktestConfig(
                mode=bt.mode,
                starting_capital=per_ticker_capital,
                min_signal_strength=bt.min_signal_strength,
                commission_pct=float(bt.commission_pct) if bt.commission_pct is not None else 0.0,
                slippage_pct=float(bt.slippage_pct) if bt.slippage_pct is not None else 0.0,
                position_size_pct=float(bt.position_size_pct) if bt.position_size_pct is not None else 100.0,
                stop_loss_pct=float(bt.stop_loss_pct) if bt.stop_loss_pct is not None else None,
                take_profit_pct=float(bt.take_profit_pct) if bt.take_profit_pct is not None else None,
            )

            # Fetch start with warmup buffer
            fetch_start = bt.start_date - timedelta(days=WARMUP_BUFFER_DAYS)

            # Run backtest per ticker
            per_ticker_results: list[tuple[str, BacktestResult]] = []
            for ticker, stock_id in tickers:
                ohlcv = await _fetch_ohlcv(session, stock_id, fetch_start, bt.end_date)
                sentiment = None
                if bt.mode == "full":
                    sentiment = await _fetch_sentiment(session, stock_id, fetch_start, bt.end_date)

                result = run_backtest(ticker, ohlcv, config, sentiment_data=sentiment)
                per_ticker_results.append((ticker, result))

            # Aggregate if sector backtest
            if len(per_ticker_results) > 1:
                final = aggregate_backtest_results(per_ticker_results, float(bt.starting_capital))
            else:
                final = per_ticker_results[0][1]

            # Store results
            bt.status = "completed"
            bt.completed_at = datetime.now(timezone.utc)
            bt.total_return_pct = final.total_return_pct
            bt.annualized_return_pct = final.annualized_return_pct
            bt.sharpe_ratio = final.sharpe_ratio
            bt.max_drawdown_pct = final.max_drawdown_pct
            bt.win_rate_pct = final.win_rate_pct
            bt.total_trades = final.total_trades
            bt.avg_win_pct = final.avg_win_pct
            bt.avg_loss_pct = final.avg_loss_pct
            bt.best_trade_pct = final.best_trade_pct
            bt.worst_trade_pct = final.worst_trade_pct
            bt.final_equity = final.final_equity

            # Serialize equity curve to JSON
            bt.equity_curve = json.dumps(
                [{"date": str(p.date), "equity": round(p.equity, 2)} for p in final.equity_curve]
            )

            # Benchmark comparison
            if final.equity_curve:
                benchmark_ticker_str = bt.benchmark_ticker or "SPY"
                bench_result = await session.execute(
                    select(Stock).where(Stock.ticker == benchmark_ticker_str)
                )
                bench_stock = bench_result.scalar_one_or_none()
                if bench_stock:
                    bench_ohlcv = await _fetch_ohlcv(session, bench_stock.id, fetch_start, bt.end_date)
                    benchmark = compute_benchmark(bench_ohlcv, final.equity_curve, float(bt.starting_capital))
                    if benchmark:
                        bt.benchmark_ticker = benchmark_ticker_str
                        bt.benchmark_total_return_pct = benchmark.total_return_pct
                        bt.benchmark_annualized_return_pct = benchmark.annualized_return_pct
                        bt.alpha = benchmark.alpha
                        bt.beta = benchmark.beta
                        bt.benchmark_equity_curve = json.dumps(
                            [{"date": str(p.date), "equity": round(p.equity, 2)} for p in benchmark.equity_curve]
                        )

            # Bulk-insert trade records
            for trade in final.trades:
                session.add(
                    BacktestTrade(
                        backtest_id=backtest_id,
                        ticker=trade.ticker,
                        action=trade.action,
                        trade_date=datetime.combine(trade.trade_date, datetime.min.time()),
                        price=trade.price,
                        shares=trade.shares,
                        position_value=trade.position_value,
                        portfolio_equity=trade.portfolio_equity,
                        signal_score=trade.signal_score,
                        signal_direction=trade.signal_direction,
                        signal_strength=trade.signal_strength,
                        return_pct=trade.return_pct,
                        exit_reason=trade.exit_reason,
                    )
                )

            await session.commit()

            logger.info(
                f"Backtest {backtest_id} completed: {final.total_trades} trades, "
                f"{final.total_return_pct:.2f}% return"
            )
            return {
                "backtest_id": backtest_id,
                "status": "completed",
                "total_trades": final.total_trades,
                "total_return_pct": final.total_return_pct,
            }

        except Exception as exc:
            bt.status = "failed"
            bt.error_message = str(exc)[:500]
            bt.completed_at = datetime.now(timezone.utc)
            await session.commit()
            raise


async def _mark_failed(backtest_id: int, error: str):
    """Mark a backtest as failed (used when outer exception handling catches errors)."""
    async with async_session() as session:
        bt = await session.get(Backtest, backtest_id)
        if bt:
            bt.status = "failed"
            bt.error_message = error[:500]
            bt.completed_at = datetime.now(timezone.utc)
            await session.commit()


async def _fetch_ohlcv(
    session: AsyncSession, stock_id: int, start: datetime, end: datetime
) -> list[OHLCVRow]:
    """Fetch OHLCV data for a stock, ordered oldest first."""
    result = await session.execute(
        select(
            MarketDataDaily.date,
            MarketDataDaily.open,
            MarketDataDaily.high,
            MarketDataDaily.low,
            MarketDataDaily.close,
            MarketDataDaily.volume,
        )
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.date >= start.date() if hasattr(start, 'date') else MarketDataDaily.date >= start)
        .where(MarketDataDaily.date <= end.date() if hasattr(end, 'date') else MarketDataDaily.date <= end)
        .where(MarketDataDaily.close != None)  # noqa: E711
        .order_by(MarketDataDaily.date.asc())
    )
    rows = result.all()
    return [
        OHLCVRow(
            date=row.date,
            open=float(row.open) if row.open else 0.0,
            high=float(row.high) if row.high else 0.0,
            low=float(row.low) if row.low else 0.0,
            close=float(row.close),
            volume=int(row.volume) if row.volume else 0,
        )
        for row in rows
    ]


async def _fetch_sentiment(
    session: AsyncSession, stock_id: int, start: datetime, end: datetime
) -> list[SentimentRow]:
    """Fetch daily aggregated sentiment for a stock."""
    result = await session.execute(
        select(
            func.date(SentimentScore.processed_at).label("day"),
            func.avg(SentimentScore.positive_score).label("avg_positive"),
            func.avg(SentimentScore.negative_score).label("avg_negative"),
            func.count(SentimentScore.id).label("article_count"),
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= start)
        .where(SentimentScore.processed_at <= end)
        .group_by(func.date(SentimentScore.processed_at))
        .order_by(func.date(SentimentScore.processed_at).asc())
    )
    rows = result.all()
    return [
        SentimentRow(
            date=row.day,
            avg_positive=float(row.avg_positive),
            avg_negative=float(row.avg_negative),
            article_count=int(row.article_count),
        )
        for row in rows
    ]
