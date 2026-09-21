# Phase 24: Daily Signal Aggregation + Learning Reset

## Problem Statement

The current outcome evaluator works at the signal level: each individual signal is compared
independently to the subsequent price move. A stock that moves up 1% on a day with 3 bullish
signals and 1 bearish signal causes the bearish signal to be labeled "wrong" — not because the
article was unreliable, but because the stock happened to go up that day. The ML trainer and
weight optimizer both learn from these noisy per-signal labels, producing adaptive weights that
correlate with random daily price movements rather than genuine component quality.

The fix: collapse all signals for a stock within a trading session into a single **daily net view**,
evaluate the net view against the price outcome, and feed only those aggregated outcomes into
the learning loop. Individual signals are preserved for the UI; only the learning layer changes.

---

## Core Design Decisions

### 1. Trading Date Assignment

Each signal is assigned a `trading_date` — the next market close it is predicting:

- Signal generated during market hours (9:30 AM–4:00 PM ET, Mon–Fri) → same calendar date
- Signal generated after close, pre-market, or on a weekend → next trading day

Implementation: query `market_data_daily WHERE date >= signal_date_ET ORDER BY date LIMIT 1`.
Store `trading_date` on the signal row at generation time.

### 2. Net View Computation

After each signal generation run (:30), upsert the daily view for the current trading date:

```
net_score = sum(signal.composite_score * sign(direction)) / sum(abs(signal.composite_score))
conviction  = abs(net_score)
direction   = "bullish" if net_score > 0 else "bearish"
signal_count = number of signals in the group
```

Weighted by composite score magnitude so a strong signal (0.8) outweighs a weak one (0.2).

Minimum conviction threshold: **|net_score| ≥ 0.20**. Views below this threshold are stored
but excluded from outcome evaluation and learning (too ambiguous to teach anything).

### 3. Outcome Windows

Keep 1 / 3 / 5 trading-day windows, same as before. All three are evaluated at the
daily-view level rather than the per-signal level. The 1-day outcome is the primary
learning signal; 3 and 5 day are secondary context.

Baseline close = most recent market close **before** trading_date.
Outcome close = close on (trading_date + N trading days).

### 4. Learning Reset on Deploy

On the same deployment as Phase 24:

**Truncate (learning layer):**
- `signal_outcomes`
- `ml_models`
- `signal_weights`
- `regime_adaptive_weights`

**Do not touch (raw data):**
- `signals`, `market_data`, `articles`, `sentiment_scores`
- `insider_transactions`, `options_activity`, `earnings_estimates`
- All user data (watchlist, alerts, portfolios, backtests)

Exposed as a one-time admin endpoint: `POST /api/admin/reset-learning-layer`
(admin-only, audit-logged, returns 202, idempotent).

---

## New DB Tables (Alembic migration `019_daily_signal_views.py`)

### `daily_signal_views`

```sql
CREATE TABLE daily_signal_views (
    id              SERIAL PRIMARY KEY,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    trading_date    DATE NOT NULL,
    net_score       FLOAT NOT NULL,          -- weighted avg composite, signed
    direction       VARCHAR(10) NOT NULL,    -- bullish / bearish
    conviction      FLOAT NOT NULL,          -- abs(net_score)
    signal_count    INTEGER NOT NULL DEFAULT 1,
    baseline_close  FLOAT,                   -- filled at evaluation time
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (stock_id, trading_date)
);
CREATE INDEX idx_daily_view_stock_date ON daily_signal_views (stock_id, trading_date DESC);
CREATE INDEX idx_daily_view_date ON daily_signal_views (trading_date DESC);
```

### `daily_signal_view_outcomes`

```sql
CREATE TABLE daily_signal_view_outcomes (
    id              SERIAL PRIMARY KEY,
    daily_view_id   INTEGER NOT NULL REFERENCES daily_signal_views(id) ON DELETE CASCADE,
    window_days     INTEGER NOT NULL,       -- 1, 3, or 5
    outcome_close   FLOAT NOT NULL,
    price_change_pct FLOAT NOT NULL,
    is_correct      BOOLEAN NOT NULL,
    evaluated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (daily_view_id, window_days)
);
```

### `signals` table — new column

```sql
ALTER TABLE signals ADD COLUMN trading_date DATE;
CREATE INDEX idx_signal_trading_date ON signals (stock_id, trading_date DESC);
```

Backfill existing rows: `UPDATE signals SET trading_date = generated_at::date` (approximate; fine for historical data since we're resetting outcomes anyway).

---

## Changed Components

### `backend/worker/tasks/signals/signal_generator.py`

1. Compute `trading_date` for each signal at generation time (next market close logic above).
   Store on `Signal.trading_date`.

2. After all signals for a ticker are persisted, call `_upsert_daily_view(session, stock_id, trading_date)`.

3. `_upsert_daily_view()`:
   - Query all signals for (stock_id, trading_date) where composite_score is not null
   - Compute net_score and conviction
   - INSERT ... ON CONFLICT (stock_id, trading_date) DO UPDATE net_score, conviction, signal_count, updated_at
   - Skip upsert if signal_count == 0

### `backend/worker/tasks/signals/outcome_evaluator.py`

**Keep** per-signal outcome writing for UI display (signal detail panel still shows whether the signal was correct). But add a second evaluation path for daily views:

1. Find daily_signal_views where:
   - conviction ≥ 0.20 (minimum threshold)
   - trading_date has passed
   - No entry yet in daily_signal_view_outcomes for this view + window

2. Use existing `_get_close_on_or_before()` and `_get_nth_trading_day_close()` helpers
   (unchanged — they already handle weekends correctly).

3. Write to `daily_signal_view_outcomes`.

The per-signal `signal_outcomes` table continues to be written for UI purposes (signal detail panel).
Only the **learning layer** (optimizer + ML) switches to reading from daily views.

### `backend/worker/tasks/signals/weight_optimizer.py`

Replace the per-signal outcome query with a daily-view outcome query:

```python
# Old: read from signal_outcomes JOIN signals
# New: read from daily_signal_view_outcomes JOIN daily_signal_views

# For each daily view outcome:
#   weight = abs(price_change_pct)  (return-weighted, same as before)
#   For each signal that contributed to this daily view:
#       component contribution = component_score * (signal.composite_score / view.net_score)
#       credit each component proportionally
```

Component crediting logic: a signal that contributed 70% of the net view's conviction gets
70% of the credit/blame for the outcome. Components within that signal are credited by their
individual scores as before.

Regime-conditional weights: same per-(sector, regime) logic, but market_regime is taken from
the majority regime label among signals in the daily view.

### `backend/worker/utils/ml_trainer.py`

Training data changes:

```python
# Old: one row per signal → feature vector of 6 component scores → label = is_correct
# New: one row per daily_view → feature vector = weighted mean of component scores
#       across all signals in the view → label = daily_view_outcome.is_correct (1-day window)
```

Weighted mean: each signal's component scores weighted by its composite_score magnitude.
This produces a single feature vector per (stock, trading_date) that represents the
aggregate view for that day.

All other ML logic unchanged (per-sector models, LightGBM, accuracy gate for promotion).

---

## New API Endpoints

### `GET /api/signals/daily-views`

Returns paginated daily net views:

```json
{
  "data": [
    {
      "ticker": "AAPL",
      "trading_date": "2026-09-22",
      "direction": "bullish",
      "net_score": 0.54,
      "conviction": 0.54,
      "signal_count": 4,
      "outcome_1d": { "price_change_pct": 1.2, "is_correct": true },
      "outcome_3d": null
    }
  ],
  "meta": { ... }
}
```

Filters: `date`, `sector`, `direction`, `min_conviction`.

### `GET /api/signals/daily-views/today`

Returns today's net views for all stocks — powers the dashboard panel.
Cached with short TTL (5 min) since it updates hourly.

### `POST /api/admin/reset-learning-layer`

Admin only. Truncates signal_outcomes, ml_models, signal_weights, regime_adaptive_weights.
Returns 202. Audit-logged. Idempotent.

---

## Dashboard Changes

### New "Today's Predictions" Panel

Replace (or sit alongside) the "10 latest signals" feed with a **Today's Predictions** table.

Layout:
```
Today's Predictions  [Sept 20]  ●Live

Ticker  Sector        Direction   Conviction  Signals  Change
NVDA    Technology    ▲ Bullish   ████░ 0.71    6       +1.4%
AAPL    Technology    ▲ Bullish   ███░░ 0.52    3         —
XOM     Energy        ▼ Bearish   ██░░░ 0.38    2         —
JPM     Financials    ▲ Bullish   ████░ 0.63    4         —
```

- Sorted by conviction descending
- Change column fills in as the trading day progresses (from market_data intraday or daily close)
- Correct predictions turn green at close, incorrect turn red
- Clicking a row navigates to stock detail

### Keep Existing Signal Feed

The "Latest Signals" feed stays on the dashboard as a secondary panel showing individual
article-level signals. Today's Predictions is the new primary view.

---

## Frontend New Components

| Component | Purpose |
|-----------|---------|
| `src/components/Dashboard/TodaysPredictionsCard.tsx` | Daily view table panel |
| `src/components/Signals/DailyViewBadge.tsx` | Conviction bar + direction label |
| `src/api/signals.ts` | Add `getDailyViews()`, `getTodaysPredictions()` |
| `src/types/index.ts` | Add `DailySignalView` interface |

---

## New ORM Models

`backend/app/models/daily_signal_view.py`

Standard SQLAlchemy 2.0 Mapped/mapped_column. Relationships:
- `DailySignalView` → `Stock` (many-to-one)
- `DailySignalView` → `DailySignalViewOutcome` (one-to-many)

---

## Pydantic Schemas

`backend/app/schemas/signal.py` — add:
- `DailySignalView` response schema
- `DailySignalViewOutcome` embedded schema
- `TodaysPredictionsResponse` for the dashboard endpoint

---

## Beat Schedule

No new scheduled tasks. The daily view upsert is a post-step inside `generate_all_signals`.
The daily view outcome evaluation is a post-step inside `evaluate_signal_outcomes`.
Both already run on the existing :30 and :45 schedule.

---

## Summary of Changes

### New Files
| File | Purpose |
|------|---------|
| `backend/app/models/daily_signal_view.py` | ORM for daily_signal_views + outcomes |
| `backend/alembic/versions/019_daily_signal_views.py` | Migration: new tables + signals.trading_date |
| `frontend/src/components/Dashboard/TodaysPredictionsCard.tsx` | Dashboard daily view panel |
| `frontend/src/components/Signals/DailyViewBadge.tsx` | Conviction/direction display |

### Modified Files
| File | Change |
|------|--------|
| `backend/worker/tasks/signals/signal_generator.py` | Compute trading_date, upsert daily view |
| `backend/worker/tasks/signals/outcome_evaluator.py` | Second pass: evaluate daily views |
| `backend/worker/tasks/signals/weight_optimizer.py` | Read from daily view outcomes |
| `backend/worker/utils/ml_trainer.py` | Training rows from daily views |
| `backend/app/api/signals.py` | daily-views + today endpoints |
| `backend/app/api/admin.py` | reset-learning-layer endpoint |
| `backend/app/schemas/signal.py` | DailySignalView schemas |
| `frontend/src/api/signals.ts` | getDailyViews, getTodaysPredictions |
| `frontend/src/types/index.ts` | DailySignalView type |
| `frontend/src/pages/DashboardPage.tsx` | Add TodaysPredictionsCard |

### Config
No new env vars needed.

---

## Unit Tests

| Test file | Coverage |
|-----------|---------|
| `test_daily_aggregation.py` | net_score weighting, conviction threshold gate, trading_date assignment (intraday/after-hours/weekend), upsert idempotency |
| `test_daily_outcome_evaluator.py` | daily view outcome evaluation, window logic, conviction gate exclusion |
| `test_weight_optimizer_daily.py` | proportional component credit from daily views, return-weighted votes |
| `test_ml_trainer_daily.py` | feature vector aggregation from daily views, label from 1d outcome |

---

## Deployment Steps

1. Run Alembic migration (`019_daily_signal_views.py`)
2. Deploy backend + frontend
3. Call `POST /api/admin/reset-learning-layer` once via admin UI or curl
4. System begins accumulating clean daily view outcomes on the next signal run
5. ML models retrain automatically at 4:30 AM once sufficient daily views accumulate (≥50 per sector)
6. Adaptive weights recompute at 4 AM

Adaptive weights and ML fall back to defaults during the accumulation period.
The system runs on the base 40/25/20/15 formula until enough clean data exists — which
is the correct honest behavior.
