# Phase 25b: Sector-Level Sentiment Signal

## Overview

Phase 25a handles multi-stock articles that pass the confidence gate by diluting
their per-stock contribution. Phase 25b handles the articles that are fully
excluded from individual stock scoring (confidence < 0.70) — instead of throwing
them away, aggregate them into a **sector-level sentiment score** and route that
back into signal generation as a small contextual component.

The insight: a macro article about semiconductor supply chains is useless as a
per-stock signal for NVDA (it's not NVDA-specific news), but it IS useful as a
sector-level mood indicator. Phase 25b captures that signal without letting it
pollute individual stock scores.

---

## Design

### What Feeds Into Sector Sentiment

Articles that currently bypass individual stock scoring entirely:

1. Articles associated with any stock in a sector at **confidence 0.30–0.69**
   (sector-spray range — currently excluded by the 0.70 gate)
2. Articles classified as `macro` or `regulatory` event category regardless
   of confidence (these describe market-wide conditions by definition)

Both groups already have FinBERT scores — the work is already done. We just
need to aggregate them differently.

### When It's Computed

Once per sector at the **start of each signal generation run** (`:30` task).
Result stored in an in-memory dict keyed by sector name, reused for all stocks
in that sector. No new DB table required.

```python
sector_sentiment_map: dict[str, float | None] = {
    "Technology": 0.32,
    "Energy": -0.15,
    "Financials": 0.08,
    "Communication Services": None,  # < MIN_ARTICLES, gate inactive
    "Consumer Discretionary": -0.22,
    "Market ETFs": 0.11,
}
```

### Score Formula

```python
MIN_ARTICLES_FOR_SECTOR = 3   # gate inactive if fewer articles
SECTOR_SENTIMENT_WINDOW_HOURS = 24

sector_sentiment[sector] = weighted_avg(
    finbert_score
    * source_credibility_weight
    * exp(-λ * hours_since_published)        # same recency decay as sentiment_momentum
    for each article where:
        any stock in sector has confidence 0.30–0.69
        OR event_category IN ('macro', 'regulatory')
        AND published_at > now - 24h
        AND quality_score >= 0.40
        AND is_canonical = True
)
# Returns None if article_count < MIN_ARTICLES_FOR_SECTOR
```

Gate: `has_sector_sentiment = sector_sentiment[stock.sector] is not None`

### Integration Into the Composite

New gated component: `sector_sentiment_score`

Weight: `WEIGHT_SECTOR_SENTIMENT = 0.05`

Small deliberately — this is contextual confirmation, not primary signal. An
individual company's earnings beat should outweigh a vague macro tailwind.

When `has_sector_sentiment=True`, the 0.05 weight distributes from the base
four proportionally, same as all other gated components.

**Signal formula changes** (`signal_formula.py`):
- Add `WEIGHT_SECTOR_SENTIMENT = 0.05`
- Add `"sector_sentiment"` to `PREDICTIVE_KEYS`
- Add `has_sector_sentiment: bool = False` parameter throughout
- `combine_component_scores()` accepts `sector_sentiment_score: float | None`

---

## What This Looks Like in Practice

**Scenario: Fed raises rates, 12 articles about impact on Financial stocks**

- All 12 articles were sector-spray confidence 0.45 → excluded from individual
  stock scores (JPM, BAC, GS etc.) ← unchanged from today
- Phase 25b aggregates these 12 articles into `sector_sentiment["Financials"]`
- If the 12 articles are net bearish → sector_sentiment ≈ -0.40
- Every Financial stock's composite gets a small -0.05 * 0.40 = -0.02 nudge
- That's the right behaviour: macro rate hike news is a slight headwind for
  all financials, but JPM's specific earnings beat still dominates its signal

**Scenario: No macro news today for Energy sector**

- Only 1 sector-level article found → below MIN_ARTICLES_FOR_SECTOR = 3
- `sector_sentiment["Energy"] = None`
- `has_sector_sentiment = False` for all Energy stocks
- Component contributes 0.0 — gate inactive, no effect

**Scenario: NVDA reports earnings beat (company-specific)**

- Article confidence = 0.95 ($NVDA) → goes into individual NVDA scoring via
  sentiment_momentum as before
- Does NOT feed sector_sentiment (confidence > 0.70 threshold, not sector-spray)
- NVDA's signal driven by company-specific news as intended

---

## New Signal Field

Add `sector_sentiment_score FLOAT NULL` to `signals` table.

Alembic migration: `021_sector_sentiment.py`

```sql
ALTER TABLE signals ADD COLUMN sector_sentiment_score FLOAT;
```

---

## Implementation Details

### `backend/worker/tasks/signals/signal_generator.py`

Add a pre-pass before the per-stock loop:

```python
async def _compute_sector_sentiment_map(
    session: AsyncSession,
    sector_names: list[str],
    now: datetime,
) -> dict[str, float | None]:
    """Aggregate low-confidence + macro articles into per-sector scores."""
    ...
```

Called once at the start of `generate_all_signals()`. Result passed into
each stock's component scoring call.

### `backend/worker/tasks/signals/component_scores.py`

Add `calc_sector_sentiment_score()`:

```python
def calc_sector_sentiment_score(
    sector_sentiment_map: dict[str, float | None],
    sector_name: str,
) -> float | None:
    """Look up pre-computed sector sentiment. None = gate inactive."""
    return sector_sentiment_map.get(sector_name)
```

This is deliberately a simple lookup — the aggregation happens in the
pre-pass, not per-stock.

### `backend/worker/utils/signal_formula.py`

Add `WEIGHT_SECTOR_SENTIMENT = 0.05` and gate logic following the existing
pattern for `has_analyst`, `has_insider` etc.

### `backend/worker/utils/backtester/signals.py`

Pass `sector_sentiment_score=None, has_sector_sentiment=False` explicitly.
Backtesting sector macro context historically is not feasible without
reprocessing all historical low-confidence article associations.

---

## Relationship to Phase 25a

The two phases are complementary and non-overlapping:

| Article type | Confidence | Phase 25a | Phase 25b |
|---|---|---|---|
| `$AAPL` mentioned | 0.95 | full weight (n=1, dilution=1.0) | not included |
| Named in multi-stock article | 0.70–0.95 | diluted by stock count | not included |
| Company name match | 0.60 | excluded (< 0.70 gate) | not included |
| Sector-spray | 0.45 | excluded (< 0.70 gate) | **fed into sector score** |
| Macro/regulatory | any | diluted + category discount | **fed into sector score** |

Together: company-specific news drives individual stock scores (Phase 25a
ensures proportional weight); sector/macro news drives sector-level context
(Phase 25b captures it as a separate component).

---

## Summary of Changes

### New Files
| File | Purpose |
|------|---------|
| `backend/alembic/versions/021_sector_sentiment.py` | Add signals.sector_sentiment_score |

### Modified Files
| File | Change |
|------|--------|
| `backend/worker/tasks/signals/signal_generator.py` | Pre-pass to compute sector_sentiment_map; pass into per-stock scoring |
| `backend/worker/tasks/signals/component_scores.py` | Add calc_sector_sentiment_score() lookup |
| `backend/worker/utils/signal_formula.py` | WEIGHT_SECTOR_SENTIMENT, has_sector_sentiment gate |
| `backend/worker/utils/backtester/signals.py` | has_sector_sentiment=False explicitly |
| `frontend/src/components/Signals/ComponentBreakdown.tsx` | Sector Sentiment bar in Gated section |
| `frontend/src/types/index.ts` | sector_sentiment_score on Signal type |

### No new DB tables. One new column on signals.

---

## Deployment

1. Run Alembic migration (`021_sector_sentiment.py`)
2. Docker VM: `git pull && make build && make up`
3. Compute VM: `git pull && sudo systemctl restart celery-worker`

No learning reset required. Sector sentiment is a new additive component —
existing daily view outcomes remain valid.

---

## Unit Tests

| Test | Coverage |
|------|---------|
| `test_sector_sentiment_aggregation.py` | weighted avg computation, recency decay, MIN_ARTICLES gate, None when sparse |
| `test_sector_sentiment_map.py` | pre-pass groups articles by sector correctly, macro category included regardless of confidence |
| `test_signal_formula_sector.py` | has_sector_sentiment gate, weight scaling with sector active |
| `test_component_scores_sector.py` | lookup returns correct value from map, None propagated correctly |
