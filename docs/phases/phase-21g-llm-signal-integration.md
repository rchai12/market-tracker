# Phase 21g — LLM Signal Integration

**Goal:** Close the loop on Phases 21d–21f by using the extracted LLM data in signal scoring.
Two changes: (1) apply `management_tone` as a modifier on the earnings score, and (2) add
`analyst_score` as a new gated signal component aggregated from analyst rating articles.

---

## Background

Phase 21d extracts `guidance_change` (stored on `EarningsEstimate`) and `management_tone`
(stored in `article.metadata_['management_tone']`) from earnings articles.
Phase 21f extracts `rating_change`, `price_target`, and `analyst_firm` from analyst_rating
articles into `article.metadata_`.

The `guidance_change` modifier on `earnings_score` is **already implemented** in
`component_scores.py:calc_earnings_surprise_score()` (lines 520–526). It applies ±0.2
based on `EarningsEstimate.guidance_change`. Management tone and analyst ratings are
currently **collected but unused**.

---

## Change 1: Management tone modifier on earnings score

**File:** `backend/worker/tasks/signals/component_scores.py`

Inside `calc_earnings_surprise_score()`, after fetching the `EarningsEstimate` row and
computing `base + guidance_boost`, add a `tone_boost` from the most recent earnings article
with LLM extraction for this stock.

**Query:** Within `calc_earnings_surprise_score`, after the existing `EarningsEstimate` query,
run a second query:

```
SELECT article.metadata_
FROM articles article
JOIN article_stocks ast ON ast.article_id = article.id
JOIN stocks s ON s.id = ast.stock_id
WHERE s.id = stock_id
  AND article.event_category = 'earnings'
  AND article.llm_extracted = true
  AND article.published_at >= now - EARNINGS_WINDOW_DAYS
ORDER BY article.published_at DESC
LIMIT 1
```

Extract `metadata_.get('management_tone')` from the result if it exists.

**Tone boost mapping:**

| management_tone | tone_boost |
|---|---|
| `"confident"` | +0.10 |
| `"cautious"` | -0.10 |
| `"neutral"` | 0.0 |
| `None` / missing | 0.0 |

**Final formula** (clamped to [-1.0, 1.0] as today):

```python
return max(-1.0, min(1.0, base + guidance_boost + tone_boost))
```

Tone modifier is ±0.10 (half of the ±0.20 guidance modifier) since tone is a softer signal
than a concrete guidance change.

**No schema/migration changes.** This is self-contained inside the existing scoring function.

---

## Change 2: Analyst score — new gated signal component

### 2a. New scoring function

**File:** `backend/worker/tasks/signals/component_scores.py`

Add `calc_analyst_score(session, stock_id, now)` following the same pattern as
`calc_options_score` and `calc_earnings_surprise_score`.

**Lookback window:** 30 days.

**Query:** Fetch all articles where:
- `event_category = 'analyst_rating'`
- `llm_extracted = true`
- Linked to `stock_id` via `ArticleStock` join
- `published_at >= now - 30 days`
- `metadata_` contains `rating_change` key

**Rating weights:**

| rating_change | weight |
|---|---|
| `"upgrade"` | +1.0 |
| `"initiate"` | +0.7 |
| `"downgrade"` | -1.0 |
| `"reiterate"` | 0.0 |
| `"maintain"` | 0.0 |
| `"none"` / missing | 0.0 |

**Gate:** If no articles have a non-zero rating weight, return `None`.

**Scoring:**

```python
# Net rating score (squash outliers with tanh)
net_rating = sum(rating_weights)
net_rating_score = math.tanh(net_rating / 2.0)

# Price target upside (optional — only when price_target present)
# Fetch most recent close from MarketDataDaily for this stock_id
current_close = ... (latest MarketDataDaily.close)
upside_values = [
    (float(pt) - current_close) / current_close
    for pt in price_targets  # metadata_['price_target'] where not None
    if current_close > 0
]
upside_score = math.tanh(sum(upside_values) / len(upside_values) * 5.0) if upside_values else 0.0

# Combine: rating direction 60%, price target upside 40%
if upside_values:
    return 0.6 * net_rating_score + 0.4 * upside_score
else:
    return net_rating_score  # Rating direction only when no price targets
```

Result is naturally bounded to approximately [-1, 1] via tanh.

---

### 2b. Signal formula — add analyst as gated component

**File:** `backend/worker/utils/signal_formula.py`

Add `WEIGHT_ANALYST = 0.07` constant.

Add `"analyst"` to `PREDICTIVE_KEYS` tuple.

Update `default_weights()` to accept `has_analyst: bool = False` and compute analyst-included
weight sets using proportional scaling of the 4 base weights. Follow the same pattern as the
existing `has_earnings` and `has_options` branches. When all three gated components are
active (earnings + options + analyst), the total gated weight is 0.25; scale the 4 base
weights down proportionally so the full set sums to 1.0.

Update `apply_component_gates()` to accept `has_analyst: bool = False` and zero
`w["analyst"]` when `False`.

Update `combine_component_scores()`:
- Add `analyst_score: float | None = None` keyword argument
- Pass `has_analyst = analyst_score is not None` to weight resolution
- Include `float(w.get("analyst", 0.0)) * analyst_val` in `raw_composite`
- Include `"analyst_score": analyst_score` in the returned dict

---

### 2c. Signal generator — compute and persist analyst score

**File:** `backend/worker/tasks/signals/signal_generator.py`

In the signal generation loop, call `calc_analyst_score()` and pass the result to
`combine_component_scores()`. Store the result in the `Signal.analyst_score` column.

---

### 2d. Database migration

**New Alembic revision** (e.g. `014_analyst_score.py`):

```sql
ALTER TABLE signals ADD COLUMN analyst_score FLOAT;
```

Nullable — `None` means the gate was inactive (no analyst data in the 30-day window).

---

### 2e. Signal ORM model

**File:** `backend/app/models/signal.py`

Add:
```python
analyst_score: Mapped[float | None] = mapped_column(Float, nullable=True)
```

---

### 2f. Signal schema

**File:** `backend/app/schemas/signal.py`

Add `analyst_score: float | None = None` to the `Signal` response schema.

---

### 2g. Signals API

**File:** `backend/app/api/signals.py`

Include `analyst_score` when constructing signal response objects, matching the pattern
used for `earnings_score` and `options_score`.

---

### 2h. Frontend — ComponentBreakdown

**File:** `frontend/src/components/Signals/ComponentBreakdown.tsx`

In the **Gated** section (alongside earnings and options bars), add an "Analyst Ratings" bar
that renders when `analyst_score !== null && analyst_score !== undefined`.

Follow the same conditional rendering pattern as the existing earnings and options bars.
Use the same `DIRECTION_COLORS` constant for coloring (positive = green, negative = red).

---

## What does NOT change

- Backtester does not replay analyst scores (historical `metadata_` is not backfilled)
- ML feature vector stays at 6 components (analyst_score excluded, consistent with options/earnings)
- Weight optimizer runs on existing 6 keys; analyst weight uses default only until enough outcomes accumulate
- LLM extraction pipeline unchanged (21e/21f already handle the data collection)
- `CLAUDE.md` beat schedule unchanged

---

## Update CLAUDE.md

Update the signal scoring section to add analyst_score:

```
composite = 0.40 * sentiment_momentum + 0.25 * sentiment_volume
          + 0.20 * price_momentum    + 0.15 * volume_anomaly
          + 0.10 * earnings_score  (gated; includes guidance_change ±0.20 and management_tone ±0.10 modifiers)
          + 0.08 * options_score   (gated; OPTIONS_FLOW_ENABLED)
          + 0.07 * analyst_score   (gated; 30-day rolling window of LLM-extracted analyst ratings)
```

Update "What's implemented" to mention analyst_score component and management_tone modifier.

Update component scoring description to list 8 scoring functions (add `calc_analyst_score`
and note the tone modifier on earnings).

---

## Tests

### Management tone modifier
- `calc_earnings_surprise_score` with `management_tone = "confident"` → result is
  `base + guidance_boost + 0.10`
- `management_tone = "cautious"` → result is `base + guidance_boost - 0.10`
- `management_tone = None` (no llm_extracted article) → result unchanged from today

### Analyst score
- One upgrade article with price_target above current close → positive score
- One downgrade article, no price_target → negative score (rating direction only)
- Mix of upgrades and downgrades → net direction determines sign
- No analyst articles → returns `None` (gate inactive)
- Only `rating_change = "none"` articles → returns `None`
- `tanh` clamping: many upgrades does not exceed 1.0

### Signal formula
- `combine_component_scores` with `analyst_score = 0.5` → analyst weight included in composite
- `combine_component_scores` with `analyst_score = None` → analyst excluded, weights renormalize
- All three gated components active → weights sum to 1.0

### API
- Signal response includes `analyst_score` field (None or float)

---

## Deployment

Requires Alembic migration on Docker VM.

```bash
# Docker VM
cd ~/market-tracker
git pull
docker compose run --rm backend alembic upgrade head
docker compose up -d backend

# Compute VM
cd /opt/stock-predictor
git pull
sudo systemctl restart celery-worker celery-beat
```
