"""Signal outcome evaluation Celery task.

Evaluates past signals against actual price movements to track accuracy.
For each non-neutral signal, checks if the predicted direction matched
the actual price change over 1, 3, and 5 trading day windows.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.market_data import MarketDataDaily
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.signals.outcome_evaluator.evaluate_signal_outcomes",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def evaluate_signal_outcomes(self):
    """Evaluate signal outcomes against actual price movements. Called at :45 by beat."""
    if not settings.feedback_enabled:
        return {"skipped": True, "reason": "feedback_disabled"}
    try:
        return run_async(_evaluate_outcomes_async())
    except Exception as exc:
        logger.error(f"Signal outcome evaluation failed: {exc}")
        raise self.retry(exc=exc)


async def _evaluate_outcomes_async() -> dict:
    """Evaluate signal accuracy against actual price movements."""
    now = datetime.now(timezone.utc)
    windows = settings.feedback_windows_list
    evaluated = 0
    skipped = 0

    async with async_session() as session:
        for window_days in windows:
            # Signals need at least window_days*2 calendar days to have market data
            # Cap lookback at 30 calendar days to avoid processing ancient signals
            cutoff_max = now - timedelta(days=window_days * 2)
            cutoff_min = now - timedelta(days=max(window_days * 2 + 14, 30))

            signals = await _get_unevaluated_signals(session, window_days, cutoff_min, cutoff_max)

            for signal in signals:
                outcome = await _evaluate_single_signal(session, signal, window_days)
                if outcome:
                    stmt = (
                        pg_insert(SignalOutcome)
                        .values(
                            signal_id=outcome.signal_id,
                            window_days=outcome.window_days,
                            signal_close=outcome.signal_close,
                            outcome_close=outcome.outcome_close,
                            price_change_pct=outcome.price_change_pct,
                            is_correct=outcome.is_correct,
                        )
                        .on_conflict_do_nothing()
                    )
                    await session.execute(stmt)
                    evaluated += 1
                else:
                    skipped += 1

        await session.commit()

    logger.info(f"Signal outcome evaluation: {evaluated} evaluated, {skipped} skipped")
    return {"evaluated": evaluated, "skipped": skipped}


async def _get_unevaluated_signals(
    session: AsyncSession,
    window_days: int,
    cutoff_min: datetime,
    cutoff_max: datetime,
) -> list[Signal]:
    """Find non-neutral signals old enough to evaluate but not yet evaluated."""
    existing_subq = (
        select(SignalOutcome.signal_id)
        .where(SignalOutcome.window_days == window_days)
        .subquery()
    )

    result = await session.execute(
        select(Signal)
        .where(Signal.direction.in_(["bullish", "bearish"]))
        .where(Signal.generated_at >= cutoff_min)
        .where(Signal.generated_at <= cutoff_max)
        .where(Signal.id.notin_(select(existing_subq.c.signal_id)))
        .order_by(Signal.generated_at.asc())
        .limit(500)
    )
    return list(result.scalars().all())


async def _evaluate_single_signal(
    session: AsyncSession, signal: Signal, window_days: int
) -> SignalOutcome | None:
    """Evaluate one signal for one window.

    1. Find close price on/before the signal date
    2. Find close price N trading days later
    3. Compute price change and correctness
    """
    signal_date = signal.generated_at.date()

    signal_close = await _get_close_on_or_before(session, signal.stock_id, signal_date)
    if signal_close is None:
        return None

    outcome_close = await _get_nth_trading_day_close(session, signal.stock_id, signal_date, window_days)
    if outcome_close is None:
        return None

    price_change_pct = (outcome_close - signal_close) / signal_close

    is_correct = (signal.direction == "bullish" and price_change_pct > 0) or (
        signal.direction == "bearish" and price_change_pct < 0
    )

    return SignalOutcome(
        signal_id=signal.id,
        window_days=window_days,
        signal_close=round(signal_close, 4),
        outcome_close=round(outcome_close, 4),
        price_change_pct=round(price_change_pct, 5),
        is_correct=is_correct,
    )


async def _get_close_on_or_before(
    session: AsyncSession, stock_id: int, target_date
) -> float | None:
    """Get the close price on or before the target date."""
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


async def _get_nth_trading_day_close(
    session: AsyncSession, stock_id: int, start_date, n: int
) -> float | None:
    """Get close price N trading days after start_date.

    Uses offset on market_data_daily which only contains trading days,
    so weekends/holidays are naturally skipped.
    """
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
