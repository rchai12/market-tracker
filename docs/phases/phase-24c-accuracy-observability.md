# Phase 24c: Daily View Accuracy Observability

## Problem

Phase 24 moved the learning loop to daily net views evaluated on excess returns.
The UI has not caught up. The Accuracy tab and dashboard accuracy widget still read
from `signal_outcomes` (per-signal, absolute returns, pre-reset data). The number
displayed — e.g. "72% accuracy" — measures a different system than what is running.

There is currently no way to see whether the composite signal is actually working.

---

## What to Measure

### 1. Daily View Accuracy (headline metric)

`% of daily net views (conviction ≥ 0.20) where excess_return_pct matched direction`

This is exactly what the optimizer and ML trainer use as `is_correct`. It should be
the primary accuracy number shown everywhere in the UI.

### 2. Conviction Calibration

If the system is well-calibrated, higher conviction should predict higher accuracy:

| Bucket | Conviction | Expected accuracy |
|--------|------------|-------------------|
| Low | 0.20–0.35 | ~52–55% |
| Medium | 0.35–0.50 | ~55–60% |
| High | 0.50–0.65 | ~60–65% |
| Very High | 0.65+ | ~65%+ |

If the buckets show no gradient, the system is not learning what it thinks it is
learning. This is the single most diagnostic chart for system health.

### 3. Average Excess Return

Binary accuracy is incomplete. A system correct 60% of the time but wrong by large
margins on the other 40% is still a bad system.

Report:
- Mean `excess_return_pct` on **correct** daily views
- Mean `excess_return_pct` on **incorrect** daily views

A working system shows a clear spread. If both cluster near zero, the predictions
are not generating meaningful alpha.

### 4. Sector Accuracy

Some sectors are inherently more predictable than others. Breaking accuracy down by
sector reveals where the composite signal is reliable vs. where it is noise.

### 5. Regime Accuracy

Does the system perform better in trending markets vs. sideways? The majority_regime
label on each daily view enables this breakdown. Useful for understanding when to
trust signals more.

---

## New API Endpoints

All under `/api/signals/daily-views/` — parallel to existing `/api/signals/accuracy/`
which is kept unchanged for backward compatibility.

### `GET /api/signals/daily-views/accuracy`

Overall daily view accuracy summary. Primary response for the headline metric.

Query params:
- `window_days` (int, default 1) — which outcome window to evaluate
- `sector` (str, optional)
- `direction` (str, optional — bullish/bearish)
- `date_from` / `date_to` (date, optional)
- `min_conviction` (float, default 0.20)

Response:
```json
{
  "total_views": 312,
  "evaluated_views": 289,
  "correct": 173,
  "accuracy_pct": 59.9,
  "avg_conviction": 0.47,
  "avg_excess_return_correct": 1.24,
  "avg_excess_return_incorrect": -0.83,
  "avg_excess_return_all": 0.31,
  "insufficient_data": false,
  "min_views_for_confidence": 50
}
```

`insufficient_data: true` when `evaluated_views < min_views_for_confidence` — the UI
shows a "still accumulating data" state rather than a misleading number.

### `GET /api/signals/daily-views/accuracy/trend`

Weekly rolling accuracy for trend chart.

Response:
```json
{
  "buckets": [
    {
      "week_start": "2026-08-01",
      "view_count": 28,
      "accuracy_pct": 57.1,
      "avg_conviction": 0.44,
      "avg_excess_return": 0.28
    }
  ]
}
```

### `GET /api/signals/daily-views/accuracy/calibration`

Accuracy bucketed by conviction level for the calibration chart.

Response:
```json
{
  "buckets": [
    {
      "label": "Low",
      "min_conviction": 0.20,
      "max_conviction": 0.35,
      "count": 89,
      "accuracy_pct": 53.9,
      "avg_excess_return": 0.12
    },
    {
      "label": "Medium",
      "min_conviction": 0.35,
      "max_conviction": 0.50,
      "count": 112,
      "accuracy_pct": 58.0,
      "avg_excess_return": 0.41
    },
    {
      "label": "High",
      "min_conviction": 0.50,
      "max_conviction": 0.65,
      "count": 67,
      "accuracy_pct": 63.4,
      "avg_excess_return": 0.89
    },
    {
      "label": "Very High",
      "min_conviction": 0.65,
      "max_conviction": 1.0,
      "count": 21,
      "accuracy_pct": 71.4,
      "avg_excess_return": 1.47
    }
  ]
}
```

### `GET /api/signals/daily-views/accuracy/sectors`

Accuracy broken down by sector.

Response:
```json
{
  "sectors": [
    {
      "sector": "Technology",
      "count": 98,
      "accuracy_pct": 62.2,
      "avg_excess_return": 0.74,
      "avg_conviction": 0.51
    }
  ]
}
```

### `GET /api/signals/daily-views/accuracy/regimes`

Accuracy broken down by majority market_regime label.

Same structure as sectors response — `regime` field instead of `sector`.

---

## Frontend Changes

### Signals Page — Accuracy Tab

Replace the current tab content (which reads `signal_outcomes`) with daily-view
accuracy components. Keep per-signal data available under a collapsed "Legacy
Per-Signal Accuracy" disclosure — it still has value for debugging individual signals
in the signal detail panel, but should not be the primary view.

**New layout:**

```
┌─────────────────────────────────────────────────────┐
│  Daily View Accuracy (last 90 days)                 │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Accuracy │  │ Avg α    │  │ Views    │          │
│  │  59.9%   │  │ +0.31%   │  │   289    │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│  ── Conviction Calibration ──────────────────────── │
│  [Bar chart: Low/Medium/High/VeryHigh vs accuracy%] │
│  [Reference line at 50%]                            │
│                                                     │
│  ── Accuracy Trend ──────────────────────────────── │
│  [Weekly line chart: accuracy % over time]          │
│                                                     │
│  ── By Sector ───────────────────────────────────── │
│  [Table: sector | views | accuracy | avg α]         │
│                                                     │
│  ▸ Legacy Per-Signal Accuracy (collapsed)           │
└─────────────────────────────────────────────────────┘
```

### Dashboard — AccuracyCard

Update the existing `AccuracyCard` component to pull from
`GET /api/signals/daily-views/accuracy` instead of the per-signal endpoint.

Show:
- Headline accuracy % (30-day, 1d window)
- Avg excess return
- Small conviction gradient indicator (3 colored dots: low/med/high conviction accuracy)

If `insufficient_data: true`, show "Building accuracy history..." with the current
evaluated view count as a progress indicator. This is the expected state right after
Phase 24's learning reset.

### Today's Predictions Card

Add a subtle context line below the card header:
`Historical accuracy: 59.9% · Avg alpha: +0.31%`

This gives the user calibration when reading today's predictions. If insufficient_data,
omit this line rather than show a misleading zero.

---

## New Frontend Components

| Component | Purpose |
|-----------|---------|
| `src/components/Signals/DailyViewAccuracyCard.tsx` | Summary stat cards (accuracy, avg α, count) |
| `src/components/Signals/ConvictionCalibrationChart.tsx` | Bar chart: conviction bucket vs accuracy |
| `src/components/Signals/DailyAccuracyTrendChart.tsx` | Weekly rolling accuracy line chart |
| `src/components/Signals/SectorAccuracyTable.tsx` | Sector breakdown table |

Reuse the existing `AccuracyTab.tsx` shell — replace the inner components rather than
rewriting the tab routing.

---

## Backend Changes

### `backend/app/api/signals.py`

Add the 5 new endpoints under the existing signals router. Each runs a single
aggregation query against `daily_signal_view_outcomes JOIN daily_signal_views
JOIN stocks JOIN sectors`.

All queries filter on `window_days = 1` by default (the primary learning signal)
and `conviction >= 0.20` (matches the learning gate).

The calibration endpoint hard-codes the 4 conviction buckets as CASE WHEN SQL.

### `backend/app/schemas/signal.py`

Add response schemas:
- `DailyViewAccuracySummary`
- `DailyViewAccuracyTrendBucket`
- `DailyViewCalibrationBucket`
- `DailyViewSectorAccuracy`
- `DailyViewRegimeAccuracy`

### Caching

Apply `@cached(ttl=300, key="signals:daily-accuracy:*")` to the new endpoints
(5-minute TTL — these aggregate historical data and don't need to be real-time).

Invalidate `signals:daily-accuracy:*` in the outcome evaluator after writing new
daily view outcomes (same place that already invalidates signals cache).

---

## Handling Insufficient Data (Post-Reset State)

The system was just reset. `daily_signal_view_outcomes` is empty or nearly empty.

Rules:
- `accuracy_pct` is only shown when `evaluated_views >= 30` (30 daily views minimum)
- Conviction calibration buckets are hidden when any bucket has `count < 10`
- Sector breakdown hides rows with `count < 5`
- All insufficiently-populated states show a neutral message with current count:
  `"Evaluated 12 of ~50 views needed for reliable accuracy metrics"`

This prevents misleading numbers in the first few weeks after the reset while
communicating to the operator that the system is collecting data.

---

## Summary of Changes

### New Files
| File | Purpose |
|------|---------|
| `frontend/src/components/Signals/DailyViewAccuracyCard.tsx` | Summary stat block |
| `frontend/src/components/Signals/ConvictionCalibrationChart.tsx` | Calibration bar chart |
| `frontend/src/components/Signals/DailyAccuracyTrendChart.tsx` | Weekly trend chart |
| `frontend/src/components/Signals/SectorAccuracyTable.tsx` | Sector breakdown |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/api/signals.py` | 5 new daily-view accuracy endpoints |
| `backend/app/schemas/signal.py` | New accuracy response schemas |
| `backend/worker/tasks/signals/outcome_evaluator.py` | Invalidate accuracy cache after daily view outcomes written |
| `frontend/src/components/Signals/AccuracyTab.tsx` | Replace content with daily-view components; collapse legacy |
| `frontend/src/components/Dashboard/AccuracyCard.tsx` | Switch to daily-view accuracy endpoint |
| `frontend/src/components/Dashboard/TodaysPredictionsCard.tsx` | Add historical accuracy context line |
| `frontend/src/api/signals.ts` | Add getDailyViewAccuracy(), getCalibration(), etc. |
| `frontend/src/types/index.ts` | New accuracy response types |

### No new migrations needed.

All new endpoints query existing `daily_signal_view_outcomes` and
`daily_signal_views` tables from Phase 24 and 24b.

---

## Unit Tests

| Test | Coverage |
|------|---------|
| `test_daily_accuracy_api.py` | Summary endpoint: correct count, accuracy_pct, avg_excess_return; insufficient_data flag at n<30 |
| `test_calibration.py` | Conviction bucket assignment, accuracy per bucket, hidden-when-thin logic |
| `test_accuracy_trend.py` | Weekly bucketing, correct week assignment |
| `test_sector_accuracy.py` | Sector join, filter by sector param |
