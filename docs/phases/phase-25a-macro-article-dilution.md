# Phase 25a: Macro Article Dilution

## Problem

The existing `SIGNAL_MIN_TICKER_CONFIDENCE = 0.70` gate already excludes pure
sector-spray articles (confidence 0.45). The remaining issue is articles that
explicitly name many companies in a sector-wide context:

> "Semiconductor stocks NVDA, AMD, INTC, QCOM, MU all surge on AI demand"

Each ticker is extracted at high confidence (0.70–0.95) and passes the gate.
Each of those 5 stocks receives a full sentiment contribution from one article
that is really describing a sector-wide trend, not a company-specific event.

A single macro article naming 10 stocks contributes 10 independent sentiment
votes — one per stock — as if it were 10 different company-specific pieces of
news. This inflates sentiment_momentum and sentiment_volume for all mentioned
stocks equally, regardless of whether the news is actually differentiated.

---

## Fix: Two-Part Solution

### Part 1 — Multi-Stock Dilution

Weight each article's sentiment contribution by how many stocks it is associated
with. The more stocks an article mentions, the less it contributes to any single
stock's score.

```python
DILUTION_SINGLE_STOCK_MAX = 3    # articles associated with ≤3 stocks = full weight
DILUTION_FLOOR = 0.20            # minimum weight regardless of stock count

def article_dilution_weight(associated_stock_count: int) -> float:
    """Full weight for company-specific articles, diminishing for sector-wide ones.

    n=1-3   → 1.0  (company-specific, full weight)
    n=5     → 0.77
    n=10    → 0.55
    n=20    → 0.39
    n=50    → 0.20 (floor)
    """
    if associated_stock_count <= DILUTION_SINGLE_STOCK_MAX:
        return 1.0
    weight = 1.0 / (associated_stock_count ** 0.35)
    return max(weight, DILUTION_FLOOR)
```

The `** 0.35` exponent gives a gentle curve — a 10-stock article still
contributes meaningfully (~55%), but a 50-stock sector sweep is close to
floor (~20%). It is not a hard cutoff, which preserves genuine sector-wide
signals (e.g. a major regulatory event affecting all tech stocks is still
real information, just not company-specific information).

### Part 2 — Macro Event Category Discount

Articles classified as `macro` or `regulatory` event categories represent
market-wide or policy-level conditions. Even when they explicitly name a
company, the news is rarely about that company specifically.

Apply an additional multiplier when the event category signals a non-company
event:

```python
EVENT_CATEGORY_WEIGHTS = {
    "earnings":   1.0,   # company-specific
    "analyst":    1.0,   # company-specific
    "insider":    1.0,   # company-specific
    "product":    1.0,   # company-specific
    "m_a":        1.0,   # company-specific
    "dividend":   1.0,   # company-specific
    "legal":      0.80,  # often sector-wide
    "regulatory": 0.60,  # usually sector/market-wide
    "macro":      0.50,  # market-wide by definition
    "general":    0.85,  # mixed
}
```

Final article weight in sentiment scoring:

```python
effective_weight = (
    source_credibility_weight        # existing
    * article_dilution_weight(n)     # new: multi-stock penalty
    * EVENT_CATEGORY_WEIGHTS[category]  # new: macro discount
)
```

---

## Where to Implement

### `backend/worker/utils/article_quality.py`

Add the two new constants and helper functions:
- `DILUTION_SINGLE_STOCK_MAX = 3`
- `DILUTION_FLOOR = 0.20`
- `EVENT_CATEGORY_WEIGHTS` dict
- `article_dilution_weight(n: int) -> float`
- `event_category_weight(category: str) -> float`

These live here alongside the existing `SIGNAL_MIN_TICKER_CONFIDENCE` and
`ARTICLE_UI_MIN_TICKER_CONFIDENCE` constants — same file owns all article
quality/weighting decisions.

### `backend/worker/tasks/signals/component_scores.py`

In `calc_sentiment_momentum()` and `calc_sentiment_volume()`:

1. Add a subquery that counts `associated_stock_count` per article:
```sql
SELECT article_id, COUNT(*) as stock_count
FROM article_stocks
WHERE confidence >= 0.70
GROUP BY article_id
```

2. Join this into the existing sentiment query.

3. Apply `article_dilution_weight(stock_count)` and
   `event_category_weight(event_category)` when accumulating the weighted
   sentiment sum.

The existing `source_credibility` weighting already happens in this function —
the new multipliers compose with it naturally.

### `backend/worker/utils/component_math.py`

If sentiment decay kernels live here (pure functions), update the weighted
sentiment accumulator to accept `dilution_weight` and `category_weight`
parameters alongside the existing `credibility_weight`. The live path passes
all three; the backtester passes `dilution_weight=1.0, category_weight=1.0`
since historical stock counts are expensive to recompute.

---

## What Does NOT Change

- `SIGNAL_MIN_TICKER_CONFIDENCE = 0.70` — unchanged, still the hard floor
- Article storage — all articles still stored regardless of stock count
- Article feed UI — all articles still visible in the feed
- Per-signal outcome evaluation — unchanged
- Daily view aggregation — unchanged

The change is purely in how much each article contributes to the weighted
sentiment sum inside `calc_sentiment_momentum()` and `calc_sentiment_volume()`.

---

## Expected Behaviour Change

**Before:** "Fed raises rates" article naming JPM, BAC, WFC, GS, MS, C (6 banks)
→ each bank gets 1.0 × credibility weight sentiment contribution

**After:** same article
→ each bank gets 0.67 × credibility weight × 0.60 (macro category)
→ effective contribution ≈ 0.40 of a company-specific article

**Before:** "NVDA earnings beat estimates by 40%" (1 stock)
→ NVDA gets 1.0 × credibility weight

**After:** same article
→ NVDA gets 1.0 × credibility weight × 1.0 (earnings category)
→ no change — company-specific articles are unaffected

---

## No Migration Required

No schema changes. `associated_stock_count` is computed at query time from the
existing `article_stocks` table. `event_category` already exists on `articles`.

---

## Config (optional)

Add to `backend/app/config.py` if tunability is wanted:
```python
article_dilution_floor: float = Field(default=0.20)
article_dilution_single_stock_max: int = Field(default=3)
```

Not strictly required since the constants are reasonable defaults.

---

## Deployment

Docker VM: `git pull && make build && make up`
Compute VM: `git pull && sudo systemctl restart celery-worker`

No migration. No learning reset required — the change affects scoring of
future signals only. The existing daily view outcomes remain valid.

---

## Unit Tests

| Test | Coverage |
|------|---------|
| `test_article_dilution.py` | dilution_weight at n=1,3,5,10,20,50; floor enforcement |
| `test_event_category_weight.py` | all 10 categories return correct multiplier |
| `test_sentiment_momentum_dilution.py` | multi-stock article contributes less than single-stock; macro article discounted vs earnings article |
