# Phase 23: ML Ensemble Promotion + Insider Trading Signal

## Overview

Two enhancements that deepen the signal intelligence pipeline:

- **Phase 23a — ML Ensemble Promotion**: The LightGBM classifiers trained in Phase 17 currently run alongside rule-based scoring for A/B comparison only. This phase promotes `ml_score` into the composite formula as a gated additive component when model quality meets a minimum threshold.

- **Phase 23b — Insider Trading Signal**: Add SEC Form 4 insider transaction tracking as a new gated signal component. Cluster insider buying is one of the strongest leading indicators. This phase fetches insider data via yfinance (same pattern as options_data.py), stores transactions in a new table, and folds net insider buying activity into the composite score.

## Disk / Resource Impact

- **23a**: No new tables or model files. LightGBM models already stored in `ml_models` table. Negligible impact.
- **23b**: New `insider_transactions` table. ~100 transactions/day across 86 tickers ≈ 36,500 rows/year at ~200 bytes each → ~7MB/year. Negligible.

---

## Part A: ML Ensemble Promotion

### Motivation

The ML classifier is trained on the same 6 component scores that drive the composite and learns non-linear interactions the linear formula cannot capture. When a model has earned sufficient accuracy on real outcomes, its vote deserves to count in the composite rather than sitting in a side-by-side comparison column.

### Gate Criteria

A model qualifies for promotion when:
- `ml_models.accuracy >= ML_MIN_ACCURACY_FOR_PROMOTION` (default 0.55)
- `ml_models.sample_count >= ML_MIN_SAMPLES_FOR_PROMOTION` (default 50)

When the gate is inactive (no qualified model), `ml_score` is stored on the signal as before but contributes 0.0 to the composite — identical to current behavior.

### Weight

`WEIGHT_ML = 0.08`

When `has_ml=True`, the base four weights scale down proportionally so the full set still sums to 1.0, identical to the existing pattern for earnings/options/analyst.

### Changes Required

#### `backend/app/config.py`
```python
ml_min_accuracy_for_promotion: float = Field(default=0.55)
ml_min_samples_for_promotion: int = Field(default=50)
```

#### `backend/worker/utils/signal_formula.py`

1. Add constants:
```python
WEIGHT_ML = 0.08
```

2. Add `"ml"` to `PREDICTIVE_KEYS` (after `"analyst"`).

3. Update `default_weights(has_ml: bool = False)` — when `has_ml=True`, add `WEIGHT_ML` to the `gated` pool and scale base weights down by `(1 - gated)`. Follow the exact same branching pattern as `has_analyst`.

4. Update `apply_component_gates(weights, has_earnings, has_options, has_analyst, has_ml=False)` — zero `w["ml"]` when `has_ml=False`, otherwise set to `WEIGHT_ML` if not already set (same as analyst pattern).

5. Update `resolve_weights()` signature to include `has_ml=False` and pass it through to `apply_component_gates`.

6. Update `combine_component_scores()`:
   - Add `ml_score: float | None = None` and `has_ml: bool = False` parameters
   - Add `ml_val = ml_score if ml_score is not None else 0.0`
   - Include `+ float(w.get("ml", 0.0)) * ml_val` in `raw_composite`
   - Return `"ml_score": ml_score` in the output dict (preserving None vs 0.0 semantics)

#### `backend/worker/tasks/signals/signal_generator.py`

After ML inference runs, determine gate:
```python
has_ml = (
    ml_score is not None
    and ml_model is not None
    and float(ml_model.accuracy or 0) >= settings.ml_min_accuracy_for_promotion
    and int(ml_model.sample_count or 0) >= settings.ml_min_samples_for_promotion
)
```

Pass `ml_score=ml_score, has_ml=has_ml` into `combine_component_scores()`.

`Signal.ml_score` is already stored separately — no model schema change needed.

#### `backend/worker/utils/backtester/signals.py`

Pass `has_ml=False` explicitly. ML models cannot be replayed historically (they didn't exist at backtest time), so the backtester always gates ML out.

#### Frontend

The ML Comparison section in ComponentBreakdown already exists. When `has_ml` is true, the ML score bar should migrate from "ML Comparison" into the **Gated** section alongside Earnings, Options, and Analyst. Update `ComponentBreakdown.tsx` to check `signal.ml_score !== null && signal.has_ml` (need to surface `has_ml` from the signal — either add a boolean field to the Signal schema or infer from `ml_confidence >= threshold`).

Methodology tab: add ML to the Gated Components column with note "Promoted when model accuracy ≥ 55%, n ≥ 50."

#### Config (.env — both VMs, optional since defaults are fine)
```
ML_MIN_ACCURACY_FOR_PROMOTION=0.55
ML_MIN_SAMPLES_FOR_PROMOTION=50
```

---

## Part B: Insider Trading Signal

### Motivation

SEC Form 4 filings are public disclosures when a corporate insider (officer, director, or >10% shareholder) buys or sells company stock. Cluster buying — multiple insiders purchasing within a short window — is one of the highest-conviction signals in quantitative finance. Sales are more ambiguous (diversification, tax planning) and are discounted.

### Data Source

**yfinance** — `yf.Ticker(ticker).insider_transactions`

Returns a DataFrame with columns: Date, Shares, Value, Insider, Position, Transaction, Type. Same pattern as `options_data.py`. No API key required, no CIK lookup, no SEC XML parsing.

Schedule: daily at **18:00 UTC** (Form 4 must be filed within 2 business days; fetching after US market close captures same-day filings).

### New DB Table

**`insider_transactions`** (new Alembic migration `015_insider_trading.py`)

```sql
CREATE TABLE insider_transactions (
    id                 SERIAL PRIMARY KEY,
    stock_id           INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    insider_name       VARCHAR(200),
    insider_title      VARCHAR(200),
    transaction_type   VARCHAR(10) NOT NULL,  -- 'P' (purchase), 'S' (sale), 'A' (award), 'D' (dispose)
    shares             NUMERIC(15, 2),
    price_per_share    NUMERIC(10, 4),
    transaction_value  NUMERIC(18, 4),        -- shares * price_per_share
    transaction_date   DATE NOT NULL,
    created_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (stock_id, insider_name, transaction_date, transaction_type, shares)
);
CREATE INDEX idx_insider_stock_date ON insider_transactions (stock_id, transaction_date DESC);
```

**New signal column**: `insider_score FLOAT NULL` on `signals` table (same migration).

### New ORM Model

`backend/app/models/insider_transaction.py`

Standard SQLAlchemy 2.0 `Mapped`/`mapped_column` model. Add `insider_transactions` relationship to `Stock` model.

### New Scraper Task

`backend/worker/tasks/scraping/insider_data.py`

```python
@celery_app.task(
    name="worker.tasks.scraping.insider_data.fetch_insider_transactions",
    ...
)
def fetch_insider_transactions():
    ...
```

**Logic:**
1. Query all active stocks from DB
2. For each ticker, call `yf.Ticker(ticker).insider_transactions`
3. Filter for last 90 days only (avoid reprocessing ancient rows)
4. Parse `transaction_type` from yfinance "Type" field ('Buy'→'P', 'Sell'→'S', 'Sale'→'S', 'Grant'→'A')
5. Upsert into `insider_transactions` using `ON CONFLICT DO NOTHING` on the unique constraint
6. Respect rate limiting: 0.5s between tickers (yfinance is lenient but avoid hammering)
7. Skip tickers where yfinance returns None or empty DataFrame

Add to `celery_app.py` includes list. Add to `beat_schedule.py`:
```python
"fetch-insider-transactions": {
    "task": "worker.tasks.scraping.insider_data.fetch_insider_transactions",
    "schedule": crontab(hour=18, minute=0),
    "options": {"queue": "scraping"},
},
```

### Signal Component Scoring

`backend/worker/tasks/signals/component_scores.py`

```python
INSIDER_WINDOW_DAYS = 30
INSIDER_NORMALIZATION = 500_000   # $500K → tanh midpoint ≈ 0.76
INSIDER_SELL_DISCOUNT = 0.40      # sells counted at 40% (noise discount)

INSIDER_ROLE_WEIGHTS = {
    # Exact match is not required — use substring matching on title
    "CEO": 1.5, "CFO": 1.5, "COO": 1.5, "President": 1.5,
    "10%": 1.5,           # "10% Owner" / "10 percent owner"
    "Director": 1.2,
    "EVP": 1.2, "SVP": 1.1, "VP": 1.0,
}
DEFAULT_ROLE_WEIGHT = 0.8

def calc_insider_score(session, stock_id: int, as_of_date) -> float | None:
    """Net signed insider buying score over the last INSIDER_WINDOW_DAYS.

    Buys contribute positively at full weight, sells at INSIDER_SELL_DISCOUNT.
    Role weight amplifies signals from senior insiders.
    Returns None (gate inactive) if no transactions exist in the window.
    Returns tanh(net_value / INSIDER_NORMALIZATION).
    """
    cutoff = as_of_date - timedelta(days=INSIDER_WINDOW_DAYS)
    rows = session.execute(
        select(InsiderTransaction)
        .where(InsiderTransaction.stock_id == stock_id)
        .where(InsiderTransaction.transaction_date >= cutoff)
        .where(InsiderTransaction.transaction_date <= as_of_date)
        .where(InsiderTransaction.transaction_type.in_(["P", "S"]))
    ).scalars().all()

    if not rows:
        return None

    net_value = 0.0
    for row in rows:
        role_w = _insider_role_weight(row.insider_title or "")
        val = float(row.transaction_value or 0)
        if row.transaction_type == "P":
            net_value += val * role_w
        elif row.transaction_type == "S":
            net_value -= val * role_w * INSIDER_SELL_DISCOUNT

    return math.tanh(net_value / INSIDER_NORMALIZATION)
```

Gate: `has_insider = insider_score is not None`

### Signal Formula Changes

`backend/worker/utils/signal_formula.py`:

1. Add `WEIGHT_INSIDER = 0.08`
2. Add `"insider"` to `PREDICTIVE_KEYS` (after `"ml"`)
3. Update all gating functions (`default_weights`, `apply_component_gates`, `resolve_weights`, `combine_component_scores`) with `has_insider: bool = False` following the exact same pattern as `has_options`

When both ML (0.08) and insider (0.08) are active alongside earnings (0.10), options (0.08), and analyst (0.07), the gated pool = 0.41; base weights scale by 0.59. The normalization in `apply_component_gates` handles this automatically.

### Signal Generator Changes

`backend/worker/tasks/signals/signal_generator.py`:

1. Call `calc_insider_score(session, stock_id, signal_date)` to get `insider_score`
2. Set `has_insider = insider_score is not None`
3. Pass both into `combine_component_scores()`
4. Store on `Signal.insider_score`

### New API Endpoint

`GET /api/market-data/{ticker}/insider-activity`

Returns 90 days of insider transactions + current insider score:

```json
{
  "insider_score": 0.42,
  "window_days": 30,
  "transactions": [
    {
      "insider_name": "Tim Cook",
      "insider_title": "CEO",
      "transaction_type": "P",
      "shares": 10000,
      "price_per_share": 189.50,
      "transaction_value": 1895000.0,
      "transaction_date": "2024-01-15"
    }
  ]
}
```

Add to `backend/app/api/market_data.py` (no new router file needed — follows the options endpoints pattern).

Add Pydantic schemas to `backend/app/schemas/market_data.py` or a new `insider.py`.

### Frontend Changes

#### `StockDetailPage` — new `StockInsiderSection.tsx`

Add below the Options section. Structure:
- "Insider Activity" heading with 30-day score pill (color-coded bullish/bearish/neutral)
- Table: Date | Insider | Title | Type | Shares | Value — buys in green, sells in muted red
- Empty state: "No insider transactions in the last 90 days"

#### `ComponentBreakdown.tsx`

Add "Insider Trading" bar in the **Gated** section when `insider_score !== null`. Label: "Insider Trading". Follows the same pattern as Earnings, Options, Analyst bars.

#### `MethodologyTab.tsx`

Add Insider Trading to the Gated Components column: "Net insider buying (30-day window, role-weighted, sells discounted 60%)."

#### `frontend/src/types/index.ts`

Add `InsiderTransaction` interface and extend `Signal` with `insider_score: number | null`.

#### `frontend/src/api/marketData.ts`

Add `getInsiderActivity(ticker: string)` API call.

### Weight Optimizer Update

`backend/worker/tasks/signals/weight_optimizer.py`

Add `"insider"` to the `components` list in `_weights_from_rows()`. Add a `_credit()` call for `insider_score` (with `min_abs=0.01` gate, same as analyst). This lets the optimizer learn whether insider signals are predictive per sector.

### Alembic Migration: `015_insider_trading.py`

1. Create `insider_transactions` table (schema above)
2. Add `insider_score FLOAT NULL` to `signals` table
3. Create index `idx_insider_stock_date`

### Config (.env — both VMs)

```
INSIDER_FLOW_ENABLED=true
```

Add to `backend/app/config.py`:
```python
insider_flow_enabled: bool = Field(default=True)
```

Gate the scraper task and signal component behind `settings.insider_flow_enabled`.

---

## Summary of Changes

### New Files
| File | Purpose |
|------|---------|
| `backend/app/models/insider_transaction.py` | ORM model for insider_transactions table |
| `backend/worker/tasks/scraping/insider_data.py` | Daily yfinance insider transaction scraper |
| `backend/alembic/versions/015_insider_trading.py` | Migration: insider_transactions table + signals.insider_score |
| `frontend/src/components/StockDetail/StockInsiderSection.tsx` | Insider activity section on stock detail page |
| `docs/phases/phase-23-ml-promotion-insider-signal.md` | This file |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/config.py` | ml_min_accuracy_for_promotion, ml_min_samples_for_promotion, insider_flow_enabled |
| `backend/worker/utils/signal_formula.py` | WEIGHT_ML, WEIGHT_INSIDER, has_ml/has_insider gates throughout |
| `backend/worker/tasks/signals/component_scores.py` | calc_insider_score(), INSIDER_* constants |
| `backend/worker/tasks/signals/signal_generator.py` | has_ml gate logic, calc_insider_score call, has_insider gate |
| `backend/worker/tasks/signals/weight_optimizer.py` | insider in _weights_from_rows() |
| `backend/worker/utils/backtester/signals.py` | has_ml=False, has_insider=False explicitly |
| `backend/worker/beat_schedule.py` | fetch-insider-transactions daily at 18:00 UTC |
| `backend/worker/celery_app.py` | include insider_data in task list |
| `backend/app/models/signal.py` | insider_score FLOAT NULL column |
| `backend/app/models/stock.py` | insider_transactions relationship |
| `backend/app/api/market_data.py` | GET /market-data/{ticker}/insider-activity endpoint |
| `frontend/src/components/Signals/ComponentBreakdown.tsx` | Insider bar in Gated section; ML bar moves to Gated when promoted |
| `frontend/src/pages/StockDetailPage.tsx` | Import and render StockInsiderSection |
| `frontend/src/api/marketData.ts` | getInsiderActivity() |
| `frontend/src/types/index.ts` | InsiderTransaction type, insider_score on Signal |

### Config vars needed on both VMs
```
INSIDER_FLOW_ENABLED=true
ML_MIN_ACCURACY_FOR_PROMOTION=0.55  # optional (has default)
ML_MIN_SAMPLES_FOR_PROMOTION=50     # optional (has default)
```

---

## Implementation Order

1. **23a first** — no new tables, simpler change, validates the gate logic
2. **23b** — requires migration, new scraper, more moving parts

Commit separately: `Phase 23a: promote ML score as gated composite component` then `Phase 23b: insider trading signal from yfinance Form 4 data`.

---

## Unit Tests

| Test file | Coverage |
|-----------|---------|
| `test_ml_promotion.py` | has_ml gate (accuracy/sample thresholds), weight scaling with ML active, backtester forces has_ml=False |
| `test_insider_score.py` | calc_insider_score: buys, sells discounted, role weights, None when no transactions, tanh clamping |
| `test_insider_scraper.py` | yfinance DataFrame parsing, transaction_type mapping, upsert dedup |
| `test_signal_formula_phase23.py` | combine_component_scores with ML + insider both active, normalization sums to 1.0 |
