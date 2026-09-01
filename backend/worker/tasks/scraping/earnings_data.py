"""Fetch earnings calendar and historical actuals from yfinance.

Runs daily at 6 AM. For each active ticker:
  1. Fetches upcoming earnings date + EPS estimate from ticker.calendar
  2. Fetches historical actuals from ticker.earnings_history
  3. Upserts into earnings_estimates table

yfinance notes:
  - ticker.calendar returns a dict. Key 'Earnings Date' is a list of Timestamps.
  - ticker.earnings_history returns a DataFrame indexed by report date with columns:
    epsEstimate, epsActual, epsDifference, surprisePercent
  - surprisePercent from yfinance is a decimal fraction (0.152 = 15.2% beat).
    We multiply by 100 before storing as surprise_pct.
  - Both calls can raise exceptions or return None/empty — handle all cases gracefully.
"""

import logging
from datetime import date, datetime, timezone

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models.earnings_estimate import EarningsEstimate
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)

# Rate limit between tickers (seconds) — yfinance is free but throttled
FETCH_DELAY_SECONDS = 0.3


@celery_app.task(
    name="worker.tasks.scraping.earnings_data.fetch_all_earnings_calendars",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def fetch_all_earnings_calendars(self):
    """Fetch earnings calendar for all active tickers. Runs daily at 6 AM."""
    try:
        return run_async(_fetch_all_async())
    except Exception as exc:
        logger.error(f"Earnings calendar fetch failed: {exc}")
        raise self.retry(exc=exc)


async def _fetch_all_async() -> dict:
    import time

    async with async_session() as session:
        result = await session.execute(
            select(Stock.ticker, Stock.id).where(Stock.is_active == True)  # noqa: E712
        )
        stocks = result.all()

    updated = 0
    errors = 0

    for ticker_str, stock_id in stocks:
        try:
            count = await _fetch_ticker(ticker_str, stock_id)
            updated += count
        except Exception as e:
            logger.warning(f"Earnings fetch failed for {ticker_str}: {e}")
            errors += 1
        time.sleep(FETCH_DELAY_SECONDS)

    logger.info(f"Earnings calendar fetch complete: {updated} records upserted, {errors} errors")
    return {"updated": updated, "errors": errors}


async def _fetch_ticker(ticker_str: str, stock_id: int) -> int:
    """Fetch and upsert earnings data for a single ticker. Returns count of records upserted."""
    ticker = yf.Ticker(ticker_str)
    records: list[dict] = []

    # ── Historical actuals from earnings_history ──────────────────────────────
    try:
        hist = ticker.earnings_history
        if hist is not None and not hist.empty:
            for report_date, row in hist.iterrows():
                # report_date is a pandas Timestamp or date
                earnings_dt = report_date.date() if hasattr(report_date, "date") else report_date

                estimated = _safe_float(row.get("epsEstimate"))
                actual = _safe_float(row.get("epsActual"))
                surprise_decimal = _safe_float(row.get("surprisePercent"))

                # yfinance returns surprisePercent as decimal fraction: 0.152 = 15.2%
                surprise_pct = round(surprise_decimal * 100, 4) if surprise_decimal is not None else None

                records.append({
                    "stock_id": stock_id,
                    "earnings_date": earnings_dt,
                    "estimated_eps": estimated,
                    "actual_eps": actual,
                    "surprise_pct": surprise_pct,
                    "reported": True,
                    "fetched_at": datetime.now(timezone.utc),
                })
    except Exception as e:
        logger.debug(f"earnings_history unavailable for {ticker_str}: {e}")

    # ── Upcoming earnings from calendar ──────────────────────────────────────
    try:
        cal = ticker.calendar
        if cal and isinstance(cal, dict):
            earnings_dates = cal.get("Earnings Date", [])
            if not isinstance(earnings_dates, list):
                earnings_dates = [earnings_dates]

            est_eps = _safe_float(cal.get("Earnings Average") or cal.get("Earnings Low"))
            est_rev = _safe_float(cal.get("Revenue Average"))

            for ed in earnings_dates:
                if ed is None:
                    continue
                earnings_dt = ed.date() if hasattr(ed, "date") else ed
                if earnings_dt < date.today():
                    continue  # already passed — covered by earnings_history
                records.append({
                    "stock_id": stock_id,
                    "earnings_date": earnings_dt,
                    "estimated_eps": est_eps,
                    "estimated_revenue": est_rev,
                    "reported": False,
                    "fetched_at": datetime.now(timezone.utc),
                })
    except Exception as e:
        logger.debug(f"calendar unavailable for {ticker_str}: {e}")

    if not records:
        return 0

    # Upsert: update on conflict (stock_id, earnings_date)
    async with async_session() as session:
        for record in records:
            stmt = pg_insert(EarningsEstimate).values(**record)
            update_cols = {
                k: stmt.excluded[k]
                for k in record
                if k not in ("stock_id", "earnings_date")
            }
            await session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_earnings_stock_date",
                    set_=update_cols,
                )
            )
        await session.commit()

    return len(records)


def _safe_float(val) -> float | None:
    """Convert value to float, returning None on failure."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (TypeError, ValueError):
        return None
