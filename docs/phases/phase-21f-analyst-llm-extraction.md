# Phase 21f — LLM Extraction for Analyst Rating Events

**Goal:** Extend the existing Claude Haiku LLM extraction pipeline to analyst articles,
extracting structured `rating_change` and `price_target` data into `article.metadata_` JSONB.
No new signal component in this phase — data enrichment only, establishing the foundation
for a future analyst consensus signal.

---

## Background

Phase 21d added LLM extraction for `event_category = 'earnings'` articles, extracting
`guidance_change` and `management_tone`. Phase 21e added a quality gate (≥ 0.60) and
reduced run frequency to every 2 hours.

Analyst upgrade/downgrade/initiation events are among the highest-impact market-moving
events in the article corpus. They are already classified as `event_category = 'analyst_rating'`
by the rule-based event classifier. Extracting structured fields from these articles gives
the research system richer data without requiring a new DB table or new signal component.

---

## Changes

### 1. Extend LLM extraction to analyst articles

**File:** `backend/worker/tasks/sentiment/llm_extraction_task.py`

Add `event_category = 'analyst_rating'` to the query that selects articles for LLM processing.
The existing conditions still apply:
- `llm_extracted IS NULL`
- `quality_score >= 0.60`
- Published within the relevant lookback window

The query should process both `'earnings'` and `'analyst_rating'` articles in the same run
via `event_category IN ('earnings', 'analyst_rating')`, subject to the existing `.limit(50)`
cap across both categories combined.

---

### 2. Add analyst extraction to the LLM extractor

**File:** `backend/worker/utils/llm_extractor.py`

Add a new extraction function `extract_analyst_data(title: str, text: str) -> dict`
alongside the existing `extract_earnings_data()`.

**Prompt:** Ask Claude Haiku to extract the following fields from the article text:

```
rating_change: one of "upgrade", "downgrade", "initiate", "reiterate", "maintain", or "none"
price_target: the analyst's price target as a number, or null if not mentioned
analyst_firm: the name of the analyst firm or bank, or null if not mentioned
```

Return a dict with those three keys. On any parse error or API failure, return
`{"rating_change": "none", "price_target": None, "analyst_firm": None}` silently
(same failure behavior as existing earnings extractor).

---

### 3. Route extraction by event category

**File:** `backend/worker/tasks/sentiment/llm_extraction_task.py`

After fetching each article, branch on `event_category`:
- `'earnings'` → call existing `extract_earnings_data()`, store results as today
- `'analyst'` → call new `extract_analyst_data()`, store results in `article.metadata_`
  under keys `rating_change`, `price_target`, `analyst_firm`

Mark `llm_extracted = True` on success for both paths.

Increment the existing skipped counter if:
- Text is empty
- `rating_change == "none"` and `price_target is None` (no useful data extracted)

---

### 4. Update CLAUDE.md

In the beat schedule description, update the LLM extraction entry:

```
every 2h :20 → LLM extraction (Claude Haiku on earnings + analyst articles with
quality_score ≥ 0.60, if LLM_EXTRACTION_ENABLED); extracts guidance_change +
management_tone (earnings) and rating_change + price_target + analyst_firm (analyst)
```

In the "What's implemented" section, update the LLM extraction bullet to mention
analyst article extraction.

---

## What does NOT change

- `.limit(50)` cap stays — shared across both event categories per run
- Quality gate `quality_score >= 0.60` applies to both categories
- Run frequency remains every 2 hours (from Phase 21e)
- No new DB table — analyst fields stored in existing `article.metadata_` JSONB
- No new signal component in this phase — data enrichment only
- Earnings extraction logic unchanged
- `ANTHROPIC_API_KEY` and `LLM_EXTRACTION_ENABLED` env vars unchanged

---

## Future use (Phase 22+)

Once analyst data is populated in `metadata_`, a future phase can:
- Aggregate analyst consensus per ticker (upgrade/downgrade ratio over rolling window)
- Add `analyst_score` as a gated signal component using rating direction + price target
  vs current price: `tanh((price_target - close) / close * 10) * rating_direction`
- Surface analyst rating history on the StockDetailPage

---

## Tests

- Add unit tests for `extract_analyst_data()` covering: upgrade with target, downgrade
  without target, initiate with firm, empty text fallback, API failure fallback
- Update the existing LLM extraction task test to assert that articles with
  `event_category = 'analyst_rating'` and `quality_score >= 0.60` are included in the query
- Assert `rating_change == "none"` and `price_target is None` increments the skipped counter

---

## Deployment

No migrations required (data stored in existing `metadata_` JSONB column).

Docker VM: rebuild backend container after git pull.
Compute VM: git pull + restart celery-worker and celery-beat (no pip changes needed).
