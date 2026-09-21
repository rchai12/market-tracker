# Phase 24b: Outcome Quality Improvements

## Overview

Three targeted improvements to how daily signal views are evaluated and aggregated.
All changes are in the learning loop only — no frontend changes required.

---

## 1. Excess Returns (Highest Impact)

### Problem

`is_correct` currently uses absolute return:
```python
is_correct = (direction == "bullish" and price_change_pct > 0)
```

On a day the market drops 2%, a bullish signal for AAPL that only falls 0.3% is labeled
**wrong** — even though AAPL outperformed by 1.7%. The weight optimizer and ML trainer
are learning to predict market direction, not stock-specific alpha.

### Fix

Evaluate `is_correct` against **excess return** (stock return minus sector ETF return):

```python
excess_return = stock_return - sector_etf_return
is_correct = (direction == "bullish" and excess_return > 0) or
             (direction == "bearish" and excess_return < 0)
```

`price_change_pct` (absolute return) is kept unchanged — the weight optimizer still uses
`abs(price_change_pct)` as vote weight since large absolute moves deserve more weight
regardless of market context.

### Sector ETF Mapping

```python
SECTOR_BENCHMARK = {
    "Energy":                "XLE",
    "Financials":            "XLF",
    "Technology":            "XLK",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Market ETFs":           None,   # absolute return for ETFs (they ARE the benchmark)
}
```

Stocks in the "Market ETFs" sector use absolute return unchanged.

### Required: Add Sector ETFs to Market Data

XLE, XLF, XLK, XLC, XLY are not currently tracked. Add them to `seed_sp500.py`
under `MARKET_ETFS` so the market data pipeline fetches their daily closes.

Run `make seed` + `make seed-history` after deployment to backfill their OHLCV.

These ETFs appear in the stocks list but that is acceptable — they are legitimate
instruments. If preferred, add a `is_benchmark` boolean to the Stock model and hide
them in the UI via a filter, but this is optional polish.

### Schema Changes

`daily_signal_view_outcomes` — two new nullable columns:

```sql
ALTER TABLE daily_signal_view_outcomes
    ADD COLUMN sector_return_pct FLOAT,
    ADD COLUMN excess_return_pct FLOAT;
```

Stored for transparency and debugging. Existing rows get NULL (they were evaluated under
the old method; the system will re-evaluate going forward).

### Implementation

`backend/worker/tasks/signals/outcome_evaluator.py`

In `_evaluate_daily_view()`:

1. Look up `stock.sector.name` for the view's stock.
2. Look up the sector ETF ticker from `SECTOR_BENCHMARK`.
3. If a benchmark ticker exists, query `market_data_daily` for the ETF's close on
   `baseline_date` and `outcome_date` (same `_get_close_on_or_before` /
   `_get_nth_trading_day_close` helpers).
4. Compute `sector_return_pct = (etf_outcome - etf_baseline) / etf_baseline`.
5. Compute `excess_return_pct = price_change_pct - sector_return_pct`.
6. Set `is_correct` based on `excess_return_pct` (or `price_change_pct` if no benchmark).

`SECTOR_BENCHMARK` mapping lives in `backend/worker/utils/daily_aggregation.py`
as a module-level constant.

---

## 2. Time-Bucketed Signals (Deduplication)

### Problem

Signals are generated hourly at :30. On a trading day (9:30 AM–4 PM ET) that is 7 runs.
Signals within the same day are correlated because the article corpus changes slowly —
a single bullish article scraped at 9 AM still dominates sentiment_momentum at 2 PM.
The net view treats 7 correlated signals as 7 independent votes, artificially inflating
conviction.

### Fix

Before computing `compute_net_view()`, reduce to one representative signal per
**4-hour time bucket**. Keep the signal with the highest `|composite_score|` per bucket
(strongest information wins).

**Buckets (ET):**
- `pre_market`: before 09:30
- `morning`: 09:30–13:30
- `afternoon`: 13:30–close (16:00)

Maximum 3 signals per stock per trading day feed the net view, each from a meaningfully
different market period.

### Implementation

Add to `backend/worker/utils/daily_aggregation.py`:

```python
BUCKET_BOUNDARIES_ET = [
    time(9, 30),   # pre_market → morning boundary
    time(13, 30),  # morning → afternoon boundary
    time(16, 0),   # afternoon → after-hours boundary
]

def _signal_bucket(generated_at: datetime) -> str:
    et = generated_at.astimezone(ET)
    t = et.time()
    if t < time(9, 30):
        return "pre_market"
    if t < time(13, 30):
        return "morning"
    return "afternoon"

def bucket_signals(signals: Sequence) -> list:
    """One signal per bucket: highest |composite_score| wins."""
    buckets: dict[str, object] = {}
    for signal in signals:
        composite = getattr(signal, "composite_score", None)
        if composite is None:
            continue
        bucket = _signal_bucket(getattr(signal, "generated_at"))
        existing = buckets.get(bucket)
        if existing is None or abs(composite) > abs(getattr(existing, "composite_score", 0)):
            buckets[bucket] = signal
    return list(buckets.values())
```

Call `bucket_signals(signals)` inside `_upsert_daily_view()` in `signal_generator.py`
before passing to `compute_net_view()`.

Add `raw_signal_count` (before bucketing) and keep `signal_count` (after bucketing)
on `daily_signal_views` so the UI can show both if useful:

```sql
ALTER TABLE daily_signal_views ADD COLUMN raw_signal_count INTEGER;
```

---

## 3. Recency Weighting

### Problem

A signal generated at 9:30 AM and one at 3:30 PM are weighted equally in the net view.
The 3:30 PM signal has seen 6 more hours of market and news activity and should count more.

### Fix

Weight each signal by exponential time decay relative to market close:

```python
RECENCY_LAMBDA = 0.15   # half-life ≈ 4.6 hours

def recency_weight(generated_at: datetime, trading_date: date) -> float:
    """1.0 at close, decays exponentially for earlier signals."""
    close_dt = datetime.combine(trading_date, MARKET_CLOSE, tzinfo=ET)
    et = generated_at.astimezone(ET)
    hours_before = max(0.0, (close_dt - et).total_seconds() / 3600.0)
    return math.exp(-RECENCY_LAMBDA * hours_before)
```

Apply inside `compute_net_view()` — multiply each signal's magnitude weight by its
recency weight before summing:

```python
effective_weight = mag * recency_weight(signal.generated_at, trading_date)
```

`trading_date` is passed as a new parameter to `compute_net_view(signals, trading_date)`.

**Effect at λ=0.15:**
| Signal time (ET) | Hours before close | Relative weight |
|------------------|--------------------|-----------------|
| 15:30            | 0.5                | 0.93            |
| 13:30            | 2.5                | 0.69            |
| 11:30            | 4.5                | 0.51            |
| 09:30            | 6.5                | 0.38            |
| Pre-market 07:00 | 9.0                | 0.26            |

After-hours signals (trading_date = next day) use their hours-before-next-close.

---

## Summary of Changes

### New Alembic Migration: `020_outcome_quality.py`

1. `ALTER TABLE daily_signal_view_outcomes ADD COLUMN sector_return_pct FLOAT`
2. `ALTER TABLE daily_signal_view_outcomes ADD COLUMN excess_return_pct FLOAT`
3. `ALTER TABLE daily_signal_views ADD COLUMN raw_signal_count INTEGER`

### Modified Files

| File | Change |
|------|--------|
| `backend/worker/utils/daily_aggregation.py` | Add `SECTOR_BENCHMARK`, `bucket_signals()`, `recency_weight()`, update `compute_net_view()` signature |
| `backend/worker/tasks/signals/signal_generator.py` | Call `bucket_signals()` before `compute_net_view()`, store `raw_signal_count` |
| `backend/worker/tasks/signals/outcome_evaluator.py` | Excess return lookup and computation in `_evaluate_daily_view()` |
| `backend/scripts/seed_sp500.py` | Add XLE, XLF, XLK, XLC, XLY to `MARKET_ETFS` |

### No frontend changes required.

The improvements propagate automatically through `is_correct`, `net_score`, and
`conviction` — the same fields the dashboard already displays.

---

## Deployment Steps

1. Add XLE/XLF/XLK/XLC/XLY to `seed_sp500.py` and run `make seed` + `make seed-history`
   (seeds the 5 ETFs and backfills their OHLCV price history)
2. Run Alembic migration (`020_outcome_quality.py`)
3. Deploy backend (Docker VM `make build && make up`)
4. Restart Celery workers (Compute VM `sudo systemctl restart celery-worker celery-beat`)

No learning reset needed — existing `daily_signal_view_outcomes` rows get NULL for the
new columns and are not re-evaluated. Clean outcomes accumulate going forward.

---

## Unit Tests

| Test | Coverage |
|------|---------|
| `test_excess_return.py` | Correct ETF lookup, excess return computation, Market ETFs fallback to absolute |
| `test_bucket_signals.py` | One signal per bucket, highest composite wins, raw_signal_count vs signal_count |
| `test_recency_weight.py` | Decay values at key times, close-of-day = 1.0, pre-market decay |
| `test_daily_aggregation.py` (update) | `compute_net_view` with trading_date parameter, combined bucket + recency |
