# Phase 21b: Earnings Surprise Signal — Implementation Specification

## Overview

The single largest driver of short-term stock price movement is the delta between reported
earnings and analyst expectations. The current system treats an earnings article with sentiment
score 0.7 identically to a product announcement with score 0.7. This phase adds a dedicated
earnings surprise signal component that captures beat/miss magnitude as a scored value.

**Data source:** yfinance (already a dependency, zero additional cost)
**New signal component:** `earnings_score` — active only within 48h after earnings are reported
**New DB table:** `earnings_estimates` — consensus estimates + actuals per ticker per quarter

The earnings component is gated: it only contributes to the composite score during the
48-hour post-reporting window. Outside that window, `calc_earnings_surprise_score` returns
`None` and the weight is effectively zero.

> **Note on adaptive weights:** The existing `SignalWeight` table (adaptive per-sector weights)
> does not have an `earnings` column. When adaptive weights are active, the earnings component
> falls back to the default weight (0.10 when active). The weight optimizer will be updated in
> Phase 21c when the full signal formula refactor occurs.

---

## Files To Read Before Implementing

- `backend/app/config.py` — settings pattern
- `backend/app/models/signal.py` — add `earnings_score` column
- `backend/worker/tasks/signals/component_scores.py` — add new scoring function
- `backend/worker/tasks/signals/signal_generator.py` — integrate earnings into composite
- `backend/worker/beat_schedule.py` — add daily earnings fetch task
- `backend/worker/celery_app.py` — add earnings task module to include list
- `backend/app/api/market_data.py` — add earnings endpoint (note: static routes before `{ticker}`)
- `backend/app/api/admin.py` — add admin trigger endpoint
- `backend/alembic/versions/008_data_quality.py` — match migration style
- `backend/alembic/env.py` — to find where models are registered for migrations

---

## Step 1: Database Migration `009_earnings_surprise`

File: `backend/alembic/versions/009_earnings_surprise.py`

```
revision = "009"
down_revision = "008"
```

> **Note:** The Phase 21b spec file for LLM extraction was drafted with revision `009`.
> That phase is deferred. This migration uses `009`. When LLM extraction is implemented
> (Phase 21d), its migration will use `010`.

### Upgrade

```python
op.create_table(
    "earnings_estimates",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("stock_id", sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"),
              nullable=False, index=True),
    sa.Column("earnings_date", sa.Date(), nullable=False, index=True),
    sa.Column("fiscal_quarter", sa.String(10), nullable=True),
    sa.Column("estimated_eps", sa.Float(), nullable=True),
    sa.Column("actual_eps", sa.Float(), nullable=True),
    sa.Column("surprise_pct", sa.Float(), nullable=True),  # stored as percentage: 15.2 = 15.2% beat
    sa.Column("estimated_revenue", sa.Float(), nullable=True),
    sa.Column("actual_revenue", sa.Float(), nullable=True),
    sa.Column("revenue_surprise_pct", sa.Float(), nullable=True),
    sa.Column("guidance_change", sa.String(20), nullable=True),  # populated by Phase 21d (LLM)
    sa.Column("reported", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.UniqueConstraint("stock_id", "earnings_date", name="uq_earnings_stock_date"),
)

op.add_column("signals", sa.Column("earnings_score", sa.Float(), nullable=True))
```

### Downgrade

```python
op.drop_column("signals", "earnings_score")
op.drop_table("earnings_estimates")
```

---

## Step 2: New ORM Model — `backend/app/models/earnings_estimate.py`

```python
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EarningsEstimate(Base):
    __tablename__ = "earnings_estimates"
    __table_args__ = (UniqueConstraint("stock_id", "earnings_date", name="uq_earnings_stock_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"),
                                          nullable=False, index=True)
    earnings_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    fiscal_quarter: Mapped[str | None] = mapped_column(String(10), nullable=True)
    estimated_eps: Mapped[float | None] = mapped_column(Float(), nullable=True)
    actual_eps: Mapped[float | None] = mapped_column(Float(), nullable=True)
    surprise_pct: Mapped[float | None] = mapped_column(Float(), nullable=True)
    estimated_revenue: Mapped[float | None] = mapped_column(Float(), nullable=True)
    actual_revenue: Mapped[float | None] = mapped_column(Float(), nullable=True)
    revenue_surprise_pct: Mapped[float | None] = mapped_column(Float(), nullable=True)
    guidance_change: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reported: Mapped[bool] = mapped_column(Boolean(), default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock")
```

After creating this file, check `backend/alembic/env.py` — if it imports models explicitly,
add `from app.models.earnings_estimate import EarningsEstimate` alongside the others.

---

## Step 3: Update `backend/app/models/signal.py`

Add one column after `ml_confidence` (or after `retail_sentiment_score` added in Phase 21a):

```python
earnings_score: Mapped[float | None] = mapped_column(Float(), nullable=True)
```

---

## Step 4: New Task File — `backend/worker/tasks/scraping/earnings_data.py`

```python
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
```

---

## Step 5: Update `backend/worker/beat_schedule.py`

Add one entry for the daily earnings fetch. Place it after `fetch-cboe-ratio`:

```python
# Earnings calendar fetch - daily at 6 AM (after overnight data is available)
"fetch-earnings-calendars": {
    "task": "worker.tasks.scraping.earnings_data.fetch_all_earnings_calendars",
    "schedule": crontab(hour=6, minute=0),
},
```

---

## Step 6: Update `backend/worker/celery_app.py`

Add to the `include` list:

```python
"worker.tasks.scraping.earnings_data",
```

---

## Step 7: Add `calc_earnings_surprise_score` to `backend/worker/tasks/signals/component_scores.py`

### 7a. Add import

```python
from app.models.earnings_estimate import EarningsEstimate
```

### 7b. Add constant

```python
EARNINGS_WINDOW_DAYS = 2  # Score is active up to 2 days after earnings_date
```

### 7c. Add function at end of file

```python
async def calc_earnings_surprise_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Earnings surprise score based on EPS beat/miss vs analyst consensus.

    Active only within EARNINGS_WINDOW_DAYS after earnings are reported.
    Returns None outside this window — the composite weight redistributes.

    Score formula:
      base = tanh(surprise_pct / 5.0)
      where surprise_pct is percentage (15.2 = 15.2% beat)

    tanh scaling: ±5% surprise → ±0.46, ±10% → ±0.76, ±15%+ → ~±0.91
    Result is bounded to [-1.0, 1.0].

    guidance_change column is NULL in Phase 21b — populated by Phase 21d (LLM extraction).
    When populated, a +0.2/-0.2 modifier will be added for raised/lowered guidance.
    """
    today = now.date() if hasattr(now, "date") else now

    result = await session.execute(
        select(EarningsEstimate)
        .where(EarningsEstimate.stock_id == stock_id)
        .where(EarningsEstimate.reported == True)  # noqa: E712
        .where(EarningsEstimate.surprise_pct.isnot(None))
        .where(EarningsEstimate.earnings_date >= today - timedelta(days=EARNINGS_WINDOW_DAYS))
        .where(EarningsEstimate.earnings_date <= today)
        .order_by(EarningsEstimate.earnings_date.desc())
        .limit(1)
    )
    earnings = result.scalar_one_or_none()

    if earnings is None:
        return None

    base = math.tanh(float(earnings.surprise_pct) / 5.0)

    # Guidance modifier: populated by LLM phase (21d); 0.0 until then
    guidance_boost = {
        "raised": 0.2,
        "lowered": -0.2,
        "maintained": 0.0,
        None: 0.0,
    }.get(earnings.guidance_change, 0.0)

    return max(-1.0, min(1.0, base + guidance_boost))
```

---

## Step 8: Update `backend/worker/tasks/signals/signal_generator.py`

### 8a. Add to import block

```python
from worker.tasks.signals.component_scores import (
    calc_earnings_surprise_score,   # new
    calc_options_score,
    calc_price_momentum,
    calc_retail_sentiment_score,
    calc_rsi_score,
    calc_sentiment_momentum,
    calc_sentiment_volume,
    calc_trend_score,
    calc_volume_anomaly,
    get_recent_article_count,
)
```

### 8b. Add new default weight constants

Add these constants alongside the existing `WEIGHT_*` constants:

```python
# Earnings-active weights (no options)
WEIGHT_SENTIMENT_MOMENTUM_EARN = 0.27
WEIGHT_SENTIMENT_VOLUME_EARN   = 0.18
WEIGHT_PRICE_MOMENTUM_EARN     = 0.13
WEIGHT_VOLUME_ANOMALY_EARN     = 0.09
WEIGHT_RSI_EARN                = 0.13
WEIGHT_TREND_EARN              = 0.10
WEIGHT_EARNINGS                = 0.10

# Earnings-active + options weights
WEIGHT_SENTIMENT_MOMENTUM_BOTH = 0.25
WEIGHT_SENTIMENT_VOLUME_BOTH   = 0.16
WEIGHT_PRICE_MOMENTUM_BOTH     = 0.12
WEIGHT_VOLUME_ANOMALY_BOTH     = 0.08
WEIGHT_RSI_BOTH                = 0.11
WEIGHT_TREND_BOTH              = 0.08
# WEIGHT_EARNINGS = 0.10 (same)
# WEIGHT_OPTIONS  = 0.08 (same)
```

### 8c. Update `_default_weights`

Replace the existing `_default_weights()` function with:

```python
def _default_weights(has_options: bool = False, has_earnings: bool = False) -> dict:
    if has_options and has_earnings:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_BOTH,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME_BOTH,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM_BOTH,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY_BOTH,
            "rsi":                WEIGHT_RSI_BOTH,
            "trend":              WEIGHT_TREND_BOTH,
            "earnings":           WEIGHT_EARNINGS,
            "options":            WEIGHT_OPTIONS,
            "source":             "default",
        }
    elif has_options:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_OPT,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME_OPT,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM_OPT,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY_OPT,
            "rsi":                WEIGHT_RSI_OPT,
            "trend":              WEIGHT_TREND_OPT,
            "earnings":           0.0,
            "options":            WEIGHT_OPTIONS,
            "source":             "default",
        }
    elif has_earnings:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_EARN,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME_EARN,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM_EARN,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY_EARN,
            "rsi":                WEIGHT_RSI_EARN,
            "trend":              WEIGHT_TREND_EARN,
            "earnings":           WEIGHT_EARNINGS,
            "options":            0.0,
            "source":             "default",
        }
    else:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY,
            "rsi":                WEIGHT_RSI,
            "trend":              WEIGHT_TREND,
            "earnings":           0.0,
            "options":            0.0,
            "source":             "default",
        }
```

### 8d. Update `_get_weights`

Add `has_earnings` parameter:

```python
def _get_weights(
    weights_map: dict | None,
    sector_id: int | None,
    has_earnings: bool = False,
) -> dict:
    """Look up adaptive weights: sector-specific -> global -> defaults.

    Note: adaptive weights (from SignalWeight table) do not yet have an
    'earnings' key. When adaptive weights are used, the earnings component
    falls back to 0.0 via w.get('earnings', 0.0) in the composite calculation.
    This will be corrected in Phase 21c when SignalWeight is updated.
    """
    if weights_map:
        if sector_id is not None and sector_id in weights_map:
            return weights_map[sector_id]
        if None in weights_map:
            return weights_map[None]
    return _default_weights(
        has_options=settings.options_flow_enabled,
        has_earnings=has_earnings,
    )
```

### 8e. Update `_compute_composite_score`

Add earnings to the function:

```python
async def _compute_composite_score(
    session: AsyncSession,
    stock_id: int,
    now: datetime,
    weights_map: dict | None = None,
    sector_id: int | None = None,
) -> dict | None:
    sent_momentum = await calc_sentiment_momentum(session, stock_id, now)
    sent_volume   = await calc_sentiment_volume(session, stock_id, now)
    price_mom     = await calc_price_momentum(session, stock_id, now)
    vol_anomaly   = await calc_volume_anomaly(session, stock_id, now)
    rsi           = await calc_rsi_score(session, stock_id, now)
    trend         = await calc_trend_score(session, stock_id, now)
    options       = await calc_options_score(session, stock_id, now)
    earnings      = await calc_earnings_surprise_score(session, stock_id, now)  # new

    article_count = await get_recent_article_count(session, stock_id, now)

    has_sentiment = sent_momentum is not None
    has_market    = price_mom is not None

    if not has_sentiment and not has_market:
        return None

    sm       = sent_momentum if sent_momentum is not None else 0.0
    sv       = sent_volume   if sent_volume   is not None else 0.0
    pm       = price_mom     if price_mom     is not None else 0.0
    va       = vol_anomaly   if vol_anomaly   is not None else 0.0
    rsi_val  = rsi           if rsi           is not None else 0.0
    trend_val= trend         if trend         is not None else 0.0
    opts_val = options       if options       is not None else 0.0
    earn_val = earnings      if earnings      is not None else 0.0

    has_earnings = earnings is not None
    w = _get_weights(weights_map, sector_id, has_earnings=has_earnings)

    composite = (
        w["sentiment_momentum"] * sm
        + w["sentiment_volume"]   * sv
        + w["price_momentum"]     * pm
        + w["volume_anomaly"]     * va
        + w["rsi"]                * rsi_val
        + w["trend"]              * trend_val
        + w.get("options", 0.0)   * opts_val
        + w.get("earnings", 0.0)  * earn_val
    )

    return {
        "composite":          composite,
        "sentiment_momentum": sm,
        "sentiment_volume":   sv,
        "price_momentum":     pm,
        "volume_anomaly":     va,
        "rsi_score":          rsi_val,
        "trend_score":        trend_val,
        "options_score":      opts_val,
        "earnings_score":     earn_val,     # new
        "article_count":      article_count,
        "weights_source":     w["source"],
    }
```

### 8f. Store `earnings_score` on the Signal object

In `_generate_signals_async`, in the `Signal(...)` constructor, add:

```python
earnings_score=round(score_data["earnings_score"], 5) if score_data.get("earnings_score") else None,
```

### 8g. Update `_build_reasoning`

Add an earnings clause after the trend section:

```python
earn_val = score_data.get("earnings_score", 0)
if earn_val and abs(earn_val) > 0.2:
    earn_dir = "beat" if earn_val > 0 else "miss"
    parts.append(f"Recent earnings {earn_dir} (score: {earn_val:.3f})")
```

---

## Step 9: New Pydantic Schema — `backend/app/schemas/earnings.py`

```python
"""Earnings estimate schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class EarningsEstimateResponse(BaseModel):
    id: int
    earnings_date: date
    fiscal_quarter: str | None
    estimated_eps: float | None
    actual_eps: float | None
    surprise_pct: float | None
    estimated_revenue: float | None
    actual_revenue: float | None
    revenue_surprise_pct: float | None
    guidance_change: str | None
    reported: bool
    fetched_at: datetime

    model_config = {"from_attributes": True}
```

---

## Step 10: New API Endpoint — `backend/app/api/market_data.py`

Add this endpoint. It must be placed **before** the `/{ticker}/daily` route to avoid
FastAPI matching `"earnings"` as a ticker parameter. The existing static route
`/cboe/put-call-ratio` already demonstrates the correct placement pattern.

Add the import at the top:

```python
from app.models.earnings_estimate import EarningsEstimate
from app.schemas.earnings import EarningsEstimateResponse
```

Add the endpoint:

```python
@router.get("/{ticker}/earnings", response_model=list[EarningsEstimateResponse])
async def get_earnings_history(
    ticker: str,
    limit: int = Query(8, ge=1, le=20),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get earnings estimate history for a ticker (last N quarters)."""
    stock = await get_stock_by_ticker(ticker, db)
    result = await db.execute(
        select(EarningsEstimate)
        .where(EarningsEstimate.stock_id == stock.id)
        .order_by(EarningsEstimate.earnings_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [EarningsEstimateResponse.model_validate(row) for row in rows]
```

---

## Step 11: Admin Endpoint — `backend/app/api/admin.py`

Add following the existing trigger pattern:

```python
@router.post("/fetch-earnings", status_code=202)
async def trigger_fetch_earnings(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Trigger earnings calendar fetch for all active tickers."""
    from worker.tasks.scraping.earnings_data import fetch_all_earnings_calendars

    task = fetch_all_earnings_calendars.delay()
    await record_audit(db, current_user.id, "fetch_earnings", "earnings_estimates", None)
    return {"task_id": task.id, "status": "queued"}
```

---

## Step 12: Frontend — Admin Page

In `frontend/src/pages/AdminPage.tsx`, add one trigger button:

- **Fetch Earnings Data** → `POST /api/admin/fetch-earnings`

Follow the existing TaskButton pattern.

---

## Step 13: Frontend — StockDetailPage Earnings Section

In `frontend/src/pages/StockDetailPage.tsx` (or the appropriate sub-component), add an
earnings section below the signal history section. The section should:

1. Fetch from `GET /api/market-data/{ticker}/earnings`
2. Display a table of recent earnings with columns:
   - **Date** — earnings report date
   - **Est. EPS** — analyst consensus
   - **Actual EPS** — reported value
   - **Surprise** — surprise_pct formatted as `+15.2%` / `-3.1%` with green/red color
   - **Status** — "Reported" or "Upcoming"
3. Highlight any row where `earnings_date` is within the last 2 days (active scoring window)

Add the API client call in `frontend/src/api/marketData.ts`:

```typescript
export const getEarningsHistory = (ticker: string, limit = 8) =>
  apiClient.get<EarningsEstimateResponse[]>(`/market-data/${ticker}/earnings`, {
    params: { limit },
  });
```

Add the type in `frontend/src/types/`:

```typescript
export interface EarningsEstimateResponse {
  id: number;
  earnings_date: string;
  fiscal_quarter: string | null;
  estimated_eps: number | null;
  actual_eps: number | null;
  surprise_pct: number | null;
  estimated_revenue: number | null;
  actual_revenue: number | null;
  revenue_surprise_pct: number | null;
  guidance_change: string | null;
  reported: boolean;
  fetched_at: string;
}
```

---

## Test Requirements

### New file: `backend/tests/test_earnings_surprise.py`

**Tests for `fetch_all_earnings_calendars` task (mock yfinance):**

| Test case | Assertion |
|---|---|
| Valid `earnings_history` DataFrame → records upserted with `reported=True` | inserted correctly |
| `surprisePercent=0.152` → stored as `surprise_pct=15.2` (×100 conversion) | percentage conversion |
| Valid `calendar` with future earnings date → record with `reported=False` | upcoming stored |
| Past date in `calendar` → skipped (covered by earnings_history) | no duplicate |
| `earnings_history` raises exception → logs warning, continues to calendar | error isolation |
| `calendar` returns None → no crash, returns 0 | null calendar handled |
| Upsert on conflict: second fetch updates `fetched_at` without duplicating | upsert correct |

**Tests for `calc_earnings_surprise_score`:**

| Test case | Assertion |
|---|---|
| Reported earnings, `surprise_pct=15.2`, within 2-day window → positive score | beat returns positive |
| Reported earnings, `surprise_pct=-8.0`, within window → negative score | miss returns negative |
| `surprise_pct=0.0` → returns 0.0 (in-line) | zero surprise |
| Earnings `earnings_date` is 3 days ago → returns None (outside window) | window respected |
| Earnings `earnings_date` is tomorrow, `reported=False` → returns None | upcoming excluded |
| `surprise_pct=100.0` → score clamped to 1.0 | bounds enforced |
| No earnings record in DB → returns None | missing data handled |
| `guidance_change="raised"` → score += 0.2 (capped at 1.0) | guidance modifier |
| `guidance_change=None` → no modifier applied | null guidance safe |

**Tests for `_default_weights` (signal_generator):**

| Test case | Assertion |
|---|---|
| `has_options=False, has_earnings=False` → standard 6-component weights | base weights |
| `has_earnings=True` → earnings weight = 0.10, total sums to 1.0 | weights sum correctly |
| `has_options=True` → options weight = 0.08, earnings = 0.0 | options path |
| `has_options=True, has_earnings=True` → both included, total sums to 1.0 | both combined |

---

## Implementation Order

1. Write migration `009_earnings_surprise` and run `make migrate` — verify with `\d earnings_estimates`
2. Write `backend/app/models/earnings_estimate.py`
3. Check `backend/alembic/env.py` — add model import if needed
4. Update `backend/app/models/signal.py` — add `earnings_score`
5. Write `backend/worker/tasks/scraping/earnings_data.py`
6. Write unit tests for earnings fetch + surprise score — all must pass before proceeding
7. Add `calc_earnings_surprise_score` to `backend/worker/tasks/signals/component_scores.py`
8. Update `backend/worker/tasks/signals/signal_generator.py` — weight constants, functions, Signal constructor
9. Write `backend/app/schemas/earnings.py`
10. Update `backend/app/api/market_data.py` — add earnings endpoint (verify route ordering)
11. Update `backend/app/api/admin.py` — add trigger endpoint
12. Update `backend/worker/beat_schedule.py` — add 6 AM task
13. Update `backend/worker/celery_app.py` — add module to include list
14. Run `make test-unit` — all must pass
15. Add admin button in `AdminPage.tsx`
16. Add earnings section to StockDetailPage
17. Add API client function and TypeScript type

---

## Post-Deploy Steps

```bash
# Docker VM
make migrate      # applies 009_earnings_surprise
make build        # new model and task files
make up

# Compute VM
git pull origin main
sudo systemctl restart celery-worker celery-beat
```

After deploy:

1. Admin → **Fetch Earnings Data** — runs the initial fetch for all 86 tickers. Takes a few
   minutes (86 tickers × 0.3s delay + yfinance network time).
2. Check the admin logs — look for `Earnings calendar fetch complete: N records upserted`
3. For any ticker currently near its earnings date, the next signal generation cycle (:30)
   should produce a non-null `earnings_score`

---

## Post-Deploy Validation Checklist

- [ ] `earnings_estimates` table exists and has rows after trigger
- [ ] `signals.earnings_score` column exists
- [ ] `GET /api/market-data/AAPL/earnings` returns records
- [ ] For a ticker that recently reported, the latest signal has `earnings_score != null`
- [ ] Signal composite score for that ticker is visibly different from surrounding days
- [ ] `make test-unit` passes
