"""Options flow data fetcher tasks.

Fetches per-ticker options chain data via yfinance and market-wide CBOE put/call ratios.
Gated behind OPTIONS_FLOW_ENABLED setting (default off).
"""

import logging
import math
import time
from datetime import date, datetime, timezone

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.cboe_put_call import CboePutCallRatio
from app.models.market_data import MarketDataDaily
from app.models.options_activity import OptionsActivity
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


def _safe_float(val) -> float | None:
    if val is None:
        return None
    v = float(val)
    return None if math.isnan(v) or math.isinf(v) else v


def _aggregate_options_chain(ticker_obj, current_price: float | None, max_expirations: int) -> dict | None:
    """Fetch and aggregate options chain data for a single ticker.

    Returns aggregated metrics dict or None on failure.
    """
    try:
        expirations = ticker_obj.options
    except Exception:
        return None

    if not expirations:
        return None

    near_expirations = expirations[:max_expirations]

    total_call_vol = 0
    total_put_vol = 0
    total_call_oi = 0
    total_put_oi = 0
    iv_volume_sum = 0.0
    iv_volume_weight = 0

    atm_call_iv = None
    atm_put_iv = None

    for exp_date in near_expirations:
        try:
            chain = ticker_obj.option_chain(exp_date)
        except Exception:
            continue

        calls = chain.calls
        puts = chain.puts

        if calls is not None and not calls.empty:
            call_vol = calls["volume"].dropna().sum()
            total_call_vol += int(call_vol) if not math.isnan(call_vol) else 0
            call_oi = calls["openInterest"].dropna().sum()
            total_call_oi += int(call_oi) if not math.isnan(call_oi) else 0

            # Volume-weighted IV from calls
            for _, row in calls.iterrows():
                vol = _safe_float(row.get("volume"))
                iv = _safe_float(row.get("impliedVolatility"))
                if vol and iv and vol > 0:
                    iv_volume_sum += iv * vol
                    iv_volume_weight += vol

        if puts is not None and not puts.empty:
            put_vol = puts["volume"].dropna().sum()
            total_put_vol += int(put_vol) if not math.isnan(put_vol) else 0
            put_oi = puts["openInterest"].dropna().sum()
            total_put_oi += int(put_oi) if not math.isnan(put_oi) else 0

            # Volume-weighted IV from puts
            for _, row in puts.iterrows():
                vol = _safe_float(row.get("volume"))
                iv = _safe_float(row.get("impliedVolatility"))
                if vol and iv and vol > 0:
                    iv_volume_sum += iv * vol
                    iv_volume_weight += vol

        # ATM IV from nearest expiration only
        if atm_call_iv is None and current_price and calls is not None and not calls.empty:
            atm_call_iv = _find_atm_iv(calls, current_price)
        if atm_put_iv is None and current_price and puts is not None and not puts.empty:
            atm_put_iv = _find_atm_iv(puts, current_price)

    total_vol = total_call_vol + total_put_vol

    # Determine data quality
    if total_vol >= settings.options_min_volume:
        data_quality = "full"
    elif total_vol >= 10:
        data_quality = "partial"
    else:
        data_quality = "stale"

    put_call_ratio = (total_put_vol / total_call_vol) if total_call_vol > 0 else None
    weighted_avg_iv = (iv_volume_sum / iv_volume_weight) if iv_volume_weight > 0 else None
    iv_skew = (atm_put_iv - atm_call_iv) if atm_put_iv is not None and atm_call_iv is not None else None

    return {
        "total_call_volume": total_call_vol,
        "total_put_volume": total_put_vol,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "put_call_ratio": round(put_call_ratio, 4) if put_call_ratio is not None else None,
        "weighted_avg_iv": round(weighted_avg_iv, 4) if weighted_avg_iv is not None else None,
        "atm_call_iv": round(atm_call_iv, 4) if atm_call_iv is not None else None,
        "atm_put_iv": round(atm_put_iv, 4) if atm_put_iv is not None else None,
        "iv_skew": round(iv_skew, 4) if iv_skew is not None else None,
        "expirations_fetched": len(near_expirations),
        "data_quality": data_quality,
    }


def _find_atm_iv(option_df, current_price: float) -> float | None:
    """Find the implied volatility of the strike nearest to current price."""
    if option_df.empty or "strike" not in option_df.columns:
        return None

    strikes = option_df["strike"].values
    if len(strikes) == 0:
        return None

    # Find nearest strike to current price
    idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - current_price))
    iv = _safe_float(option_df.iloc[idx].get("impliedVolatility"))
    return iv


async def _get_tickers_with_prices() -> list[dict]:
    """Get active tickers with their latest close prices."""
    async with async_session() as session:
        # Subquery: latest date per stock
        from sqlalchemy import func

        latest_date_sq = (
            select(
                MarketDataDaily.stock_id,
                func.max(MarketDataDaily.date).label("max_date"),
            )
            .group_by(MarketDataDaily.stock_id)
            .subquery()
        )

        result = await session.execute(
            select(Stock.id, Stock.ticker, MarketDataDaily.close)
            .join(latest_date_sq, Stock.id == latest_date_sq.c.stock_id)
            .join(
                MarketDataDaily,
                (MarketDataDaily.stock_id == latest_date_sq.c.stock_id)
                & (MarketDataDaily.date == latest_date_sq.c.max_date),
            )
            .where(Stock.is_active == True)  # noqa: E712
        )
        return [{"id": r.id, "ticker": r.ticker, "close": float(r.close) if r.close else None} for r in result.all()]


async def _store_options_data(stock_id: int, today: date, metrics: dict) -> None:
    """Upsert options activity row."""
    async with async_session() as session:
        values = {
            "stock_id": stock_id,
            "date": today,
            **metrics,
        }
        stmt = pg_insert(OptionsActivity).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_options_activity_stock_id_date",
            set_={k: stmt.excluded[k] for k in metrics},
        )
        await session.execute(stmt)
        await session.commit()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def fetch_all_options_data(self):
    """Fetch options chain data for all active tickers via yfinance.

    Scheduled at :10 on weekdays. Gated on OPTIONS_FLOW_ENABLED.
    """
    if not settings.options_flow_enabled:
        return {"status": "disabled"}
    try:
        return run_async(_fetch_all_options_async())
    except Exception as exc:
        logger.error("Options data fetch failed: %s", exc)
        raise self.retry(exc=exc)


async def _fetch_all_options_async() -> dict:
    """Fetch and store options data for all active tickers."""
    stocks = await _get_tickers_with_prices()
    if not stocks:
        logger.warning("No active tickers found for options fetch")
        return {"status": "no_tickers", "count": 0}

    logger.info("Fetching options data for %d tickers", len(stocks))

    today = date.today()
    fetched = 0
    errors = 0

    for stock_info in stocks:
        ticker = stock_info["ticker"]
        try:
            ticker_obj = yf.Ticker(ticker)
            metrics = _aggregate_options_chain(
                ticker_obj,
                stock_info["close"],
                settings.options_max_expirations,
            )
            if metrics is None:
                logger.debug("No options data available for %s", ticker)
                continue

            await _store_options_data(stock_info["id"], today, metrics)
            fetched += 1
        except Exception as e:
            logger.error("Failed to fetch options for %s: %s", ticker, e)
            errors += 1

        time.sleep(settings.options_fetch_delay)

    logger.info("Options data complete: %d fetched, %d errors", fetched, errors)
    return {"status": "complete", "tickers_fetched": fetched, "errors": errors}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def fetch_cboe_ratio(self):
    """Fetch market-wide CBOE put/call ratio from public CSV.

    Scheduled at :12 on weekdays. Runs independently of OPTIONS_FLOW_ENABLED
    since it's useful market context regardless.
    """
    if not settings.options_flow_enabled:
        return {"status": "disabled"}
    try:
        return run_async(_fetch_cboe_async())
    except Exception as exc:
        logger.error("CBOE ratio fetch failed: %s", exc)
        raise self.retry(exc=exc)


async def _fetch_cboe_async() -> dict:
    """Fetch and store CBOE put/call ratio from public CSV."""
    import io

    import httpx

    url = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as e:
        logger.error("Failed to fetch CBOE CSV: %s", e)
        return {"status": "error", "message": str(e)}

    # Parse CSV — columns: DATE, CALL, PUT, TOTAL, P/C RATIO, etc.
    lines = resp.text.strip().split("\n")
    if len(lines) < 2:
        return {"status": "empty"}

    # Find the last valid data row
    header = lines[0].lower().split(",")
    last_row = lines[-1].split(",")

    try:
        date_idx = 0  # First column is typically date
        row_date = datetime.strptime(last_row[date_idx].strip(), "%m/%d/%Y").date()
    except (ValueError, IndexError):
        logger.error("Failed to parse CBOE CSV date from: %s", last_row)
        return {"status": "parse_error"}

    # Extract ratios — CBOE CSV format varies, look for ratio columns
    total_pc = None
    equity_pc = None
    index_pc = None

    for i, col in enumerate(header):
        col = col.strip().lower()
        if i < len(last_row):
            val = _safe_float(last_row[i].strip()) if last_row[i].strip() else None
            if "total" in col and ("ratio" in col or "p/c" in col):
                total_pc = val
            elif "equity" in col and ("ratio" in col or "p/c" in col):
                equity_pc = val
            elif "index" in col and ("ratio" in col or "p/c" in col):
                index_pc = val

    # If we couldn't find labeled ratio columns, try positional fallback
    # Common CBOE format: Date, Calls, Puts, Total, P/C Ratio
    if total_pc is None and len(last_row) >= 5:
        total_pc = _safe_float(last_row[4].strip()) if last_row[4].strip() else None

    async with async_session() as session:
        stmt = pg_insert(CboePutCallRatio).values(
            date=row_date,
            total_pc=total_pc,
            equity_pc=equity_pc,
            index_pc=index_pc,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={
                "total_pc": stmt.excluded.total_pc,
                "equity_pc": stmt.excluded.equity_pc,
                "index_pc": stmt.excluded.index_pc,
            },
        )
        await session.execute(stmt)
        await session.commit()

    logger.info("CBOE ratio stored for %s: total=%.4f", row_date, total_pc or 0)
    return {"status": "complete", "date": str(row_date), "total_pc": total_pc}
