"""Insider Form 4 transaction fetcher.

Pulls yfinance `Ticker.insider_transactions` for active tickers and upserts
the last 90 days. Gated behind INSIDER_FLOW_ENABLED.
"""

import logging
import math
import time
from datetime import UTC, date, datetime, timedelta

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.insider_transaction import InsiderTransaction
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)

INSIDER_LOOKBACK_DAYS = 90

_TYPE_ALIASES = {
    "buy": "P",
    "purchase": "P",
    "p": "P",
    "sell": "S",
    "sale": "S",
    "s": "S",
    "grant": "A",
    "award": "A",
    "a": "A",
    "dispose": "D",
    "disposition": "D",
    "d": "D",
}

_DATE_COLUMNS = ("Start Date", "Date", "startDate", "start_date")
_NAME_COLUMNS = ("Insider", "filerName", "Name", "Insider Trading")
_TITLE_COLUMNS = ("Position", "Title", "Relationship", "filerRelation")
_TYPE_COLUMNS = ("Type", "Transaction", "transactionText", "Text")
_SHARES_COLUMNS = ("Shares", "#Shares", "shares")
_VALUE_COLUMNS = ("Value", "Value ($)", "value")


def map_transaction_type(raw: object) -> str | None:
    """Map a yfinance Type/Transaction string to P/S/A/D."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text or text == "nan":
        return None
    if text in _TYPE_ALIASES:
        return _TYPE_ALIASES[text]
    for key, code in _TYPE_ALIASES.items():
        if key in text:
            return code
    return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, str):
        val = val.replace(",", "").replace("$", "").strip()
        if not val:
            return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if hasattr(val, "to_pydatetime"):
        try:
            return val.to_pydatetime().date()
        except Exception:
            return None
    if isinstance(val, (int, float)):
        if math.isnan(val):
            return None
        ts = float(val)
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=UTC).date()
        except (OSError, OverflowError, ValueError):
            return None
    text = str(val).strip()
    if not text or text.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _first_present(row: dict, names: tuple[str, ...]):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        key = name.lower()
        if key in lowered and lowered[key] is not None:
            return lowered[key]
    return None


def parse_insider_dataframe(df, cutoff: date) -> list[dict]:
    """Normalize a yfinance insider_transactions DataFrame into row dicts."""
    if df is None or getattr(df, "empty", True):
        return []

    records: list[dict] = []
    for _, raw in df.iterrows():
        row = raw.to_dict()
        tx_date = _parse_date(_first_present(row, _DATE_COLUMNS))
        if tx_date is None or tx_date < cutoff:
            continue
        tx_type = map_transaction_type(_first_present(row, _TYPE_COLUMNS))
        if tx_type is None:
            continue
        shares = _safe_float(_first_present(row, _SHARES_COLUMNS))
        value = _safe_float(_first_present(row, _VALUE_COLUMNS))
        price = None
        if shares and shares != 0 and value is not None:
            price = value / shares
        name = _first_present(row, _NAME_COLUMNS)
        title = _first_present(row, _TITLE_COLUMNS)
        name_str = str(name).strip() if name is not None and str(name).strip().lower() != "nan" else ""
        title_str = str(title).strip() if title is not None and str(title).strip().lower() != "nan" else None
        records.append(
            {
                "insider_name": name_str[:200] if name_str else "",
                "insider_title": title_str[:200] if title_str else None,
                "transaction_type": tx_type,
                "shares": round(shares, 2) if shares is not None else None,
                "price_per_share": round(price, 4) if price is not None else None,
                "transaction_value": round(value, 4) if value is not None else None,
                "transaction_date": tx_date,
            }
        )
    return records


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="worker.tasks.scraping.insider_data.fetch_insider_transactions",
)
def fetch_insider_transactions(self):
    """Fetch Form 4 insider transactions for all active tickers via yfinance.

    Scheduled daily at 18:00 UTC. Gated on INSIDER_FLOW_ENABLED.
    """
    if not settings.insider_flow_enabled:
        return {"status": "disabled"}
    try:
        return run_async(_fetch_all_insider_async())
    except Exception as exc:
        logger.error("Insider transaction fetch failed: %s", exc)
        raise self.retry(exc=exc)


async def _fetch_all_insider_async() -> dict:
    async with async_session() as session:
        result = await session.execute(select(Stock.id, Stock.ticker).where(Stock.is_active == True))  # noqa: E712
        stocks = [{"id": r.id, "ticker": r.ticker} for r in result.all()]

    if not stocks:
        logger.warning("No active tickers found for insider fetch")
        return {"status": "no_tickers", "count": 0}

    logger.info("Fetching insider transactions for %d tickers", len(stocks))
    cutoff = date.today() - timedelta(days=INSIDER_LOOKBACK_DAYS)
    fetched = 0
    stored = 0
    errors = 0

    for stock_info in stocks:
        ticker = stock_info["ticker"]
        try:
            df = yf.Ticker(ticker).insider_transactions
            rows = parse_insider_dataframe(df, cutoff)
            if not rows:
                continue
            n = await _store_insider_rows(stock_info["id"], rows)
            fetched += 1
            stored += n
        except Exception as e:
            logger.error("Failed to fetch insider transactions for %s: %s", ticker, e)
            errors += 1
        time.sleep(settings.insider_fetch_delay)

    logger.info("Insider fetch complete: %d tickers, %d rows stored, %d errors", fetched, stored, errors)
    return {"status": "complete", "tickers_fetched": fetched, "rows_stored": stored, "errors": errors}


async def _store_insider_rows(stock_id: int, rows: list[dict]) -> int:
    if not rows:
        return 0
    async with async_session() as session:
        for row in rows:
            stmt = pg_insert(InsiderTransaction).values(stock_id=stock_id, **row)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_insider_tx_dedup")
            await session.execute(stmt)
        await session.commit()
    return len(rows)
