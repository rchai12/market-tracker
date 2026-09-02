# Phase 21d: LLM Extraction via Google Gemini Flash — Implementation Specification

## Overview

FinBERT classifies articles as positive/negative/neutral but cannot understand **what** happened.
Two articles with identical FinBERT scores — "Company beat earnings and raised full-year guidance"
vs "Company beat earnings but warned of macro headwinds" — will score differently in practice but
identically under FinBERT. The difference is in the forward-looking content.

This phase adds a targeted LLM extraction step that processes **earnings-related articles only**,
using Google Gemini Flash to extract two structured fields:

1. **`guidance_change`** — did management raise, lower, or maintain full-year guidance?
   Stored on `earnings_estimates` and activates the ±0.2 guidance boost in
   `calc_earnings_surprise_score` (the hook was coded in Phase 21b, awaiting this data).

2. **`management_tone`** — overall management commentary tone: confident / cautious / neutral.
   Stored in `articles.metadata_["management_tone"]` (no schema change needed, JSONB already exists).

Processing is strictly **opt-in** (`LLM_EXTRACTION_ENABLED=false` default), filtered to
high-quality earnings articles, and token-capped to keep costs minimal.

> **Cost estimate:** Gemini 1.5 Flash at $0.075/M input + $0.30/M output.
> ~300 input tokens + ~30 output tokens per article = ~$0.000032 per article.
> Processing 50 earnings articles/day ≈ $0.0016/day (~$0.05/month).
> Well within the Google AI free tier (15 RPM, 1M tokens/day) — effectively free.

> **Dependency:** Phase 21b must be merged and deployed first. This phase fills
> `earnings_estimates.guidance_change` (defined in Phase 21b migration 009) and uses the
> `EarningsEstimate` ORM model. Do not implement Phase 21d until `009_earnings_surprise`
> migration exists in the DB.

---

## Files To Read Before Implementing

- `backend/app/config.py` — add new settings
- `backend/app/models/article.py` — `metadata_` JSONB field (no change needed)
- `backend/app/models/earnings_estimate.py` — `guidance_change` column (from Phase 21b)
- `backend/worker/tasks/sentiment/sentiment_task.py` — integration point pattern
- `backend/worker/celery_app.py` — add new task module to include list
- `backend/worker/beat_schedule.py` — add scheduled run
- `backend/app/api/admin.py` — add admin trigger
- `backend/alembic/versions/011_fix_win_rate_precision.py` — match migration style (down_revision = "011")
- `pyproject.toml` — add `anthropic` dependency

---

## Step 1: Add `google-generativeai` Dependency

In `pyproject.toml`, add to the dependencies list:

```toml
"google-generativeai>=0.8.0",
```

This is the official Google Generative AI Python SDK for Gemini models. Use the sync client
(same pattern as other sync-in-async operations in the codebase). Do NOT use the REST API directly.

---

## Step 2: Database Migration `012_llm_extraction`

File: `backend/alembic/versions/012_llm_extraction.py`

```
revision = "012"
down_revision = "011"
```

### Upgrade

```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    # Track which articles have been submitted to LLM extraction.
    # NULL = not yet attempted; True = extracted; False = attempted but failed/skipped.
    op.add_column(
        "articles",
        sa.Column("llm_extracted", sa.Boolean(), nullable=True, server_default=sa.text("NULL")),
    )
    op.create_index("ix_articles_llm_extracted", "articles", ["llm_extracted"])
```

### Downgrade

```python
def downgrade() -> None:
    op.drop_index("ix_articles_llm_extracted", "articles")
    op.drop_column("articles", "llm_extracted")
```

---

## Step 3: Update `backend/app/models/article.py`

Add the `llm_extracted` column after `canonical_article_id`:

```python
llm_extracted: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None, index=True)
```

---

## Step 4: Update `backend/app/config.py`

Add new settings to the `Settings` class:

```python
# LLM extraction (Gemini Flash for earnings guidance)
llm_extraction_enabled: bool = False
gemini_api_key: str = ""
llm_max_article_chars: int = 1500   # character limit sent to LLM (cost control)
llm_rate_limit_seconds: float = 2.0  # delay between API calls (free tier: 15 RPM max)
```

---

## Step 5: New Utility — `backend/worker/utils/llm_extractor.py`

```python
"""LLM-based structured extraction from financial news articles.

Uses Google Gemini Flash to extract earnings guidance changes and management tone
from earnings-related articles. Returns structured JSON.

Cost control:
- Only called for articles with event_category = "earnings"
- Article text capped at settings.llm_max_article_chars (default 1500 chars)
- Rate limited by caller (llm_rate_limit_seconds, default 2.0s → ~30 RPM max,
  safely under the free-tier limit of 15 RPM with 2s delay)
- Fails silently (returns None) on any API or parsing error

Output schema:
  {
    "guidance_change": "raised" | "lowered" | "maintained" | "none" | null,
    "management_tone": "confident" | "cautious" | "neutral" | null
  }
"""

import json
import logging

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-1.5-flash"

EXTRACTION_PROMPT = """\
You are extracting structured data from a financial earnings news article.

Article title: {title}
Article text (may be truncated): {text}

Reply ONLY with a JSON object matching this exact schema:
{{
  "guidance_change": "raised" | "lowered" | "maintained" | "none" | null,
  "management_tone": "confident" | "cautious" | "neutral" | null
}}

Definitions:
- guidance_change:
  "raised"      = company explicitly raised full-year earnings or revenue guidance
  "lowered"     = company explicitly lowered or withdrew guidance
  "maintained"  = company reaffirmed existing guidance without change
  "none"        = guidance is not mentioned in this article
  null          = cannot determine from the text

- management_tone: overall tone of management commentary
  "confident"   = optimistic language, strong outlook, positive forward statements
  "cautious"    = hedging, uncertainty, headwinds, macro concerns mentioned
  "neutral"     = balanced or factual, no strong directional language
  null          = management commentary not present

Output ONLY the JSON object. No explanation, no markdown, no extra text.\
"""


def extract_earnings_context(
    title: str,
    article_text: str,
    max_chars: int = 1500,
) -> dict | None:
    """Call Gemini Flash to extract guidance_change and management_tone.

    Returns dict with keys 'guidance_change' and 'management_tone', or None on failure.
    All exceptions are caught and logged — never raises to caller.
    """
    try:
        import google.generativeai as genai
        from app.config import settings

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        text_snippet = (article_text or "")[:max_chars]
        prompt = EXTRACTION_PROMPT.format(title=title, text=text_snippet)

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=64,
                temperature=0.0,   # deterministic output for structured extraction
            ),
        )

        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        # Parse JSON response
        result = json.loads(raw)

        valid_guidance = {"raised", "lowered", "maintained", "none", None}
        valid_tone = {"confident", "cautious", "neutral", None}

        guidance = result.get("guidance_change")
        tone = result.get("management_tone")

        # Validate — reject unexpected values rather than storing garbage
        if guidance not in valid_guidance:
            guidance = None
        if tone not in valid_tone:
            tone = None

        return {"guidance_change": guidance, "management_tone": tone}

    except Exception as e:
        logger.warning(f"LLM extraction failed: {type(e).__name__}: {e}")
        return None
```

> **Note on markdown stripping:** Gemini Flash occasionally wraps JSON in triple-backtick
> code fences even when instructed not to. The code above handles this gracefully.

---

## Step 6: New Celery Task — `backend/worker/tasks/sentiment/llm_extraction_task.py`

```python
"""Celery task: run LLM extraction on unprocessed earnings articles.

Finds articles where:
  - event_category = 'earnings'
  - llm_extracted IS NULL (not yet attempted)
  - quality_score >= QUALITY_THRESHOLD (or NULL, for legacy articles)
  - source NOT in SIGNAL_EXCLUDED_SOURCES (no Reddit)
  - canonical_article_id IS NULL (canonical only, no duplicates)
  - published_at within last 7 days (recent only)

For each article:
  1. Calls Claude Haiku → {guidance_change, management_tone}
  2. Stores management_tone in article.metadata_["management_tone"]
  3. Finds matching EarningsEstimate (same ticker, earnings_date within ±7 days of published_at)
  4. If found, updates guidance_change on the EarningsEstimate
  5. Marks article.llm_extracted = True

Runs at :20 (after sentiment at :15, before signals at :30).
Skipped entirely when LLM_EXTRACTION_ENABLED=false.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.article import Article, ArticleStock
from app.models.earnings_estimate import EarningsEstimate
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.article_quality import QUALITY_THRESHOLD, SIGNAL_EXCLUDED_SOURCES
from worker.utils.async_task import run_async
from worker.utils.llm_extractor import extract_earnings_context

logger = logging.getLogger(__name__)

RECENT_DAYS = 7           # Only process articles published within this window
EARNINGS_MATCH_DAYS = 7   # Match article to EarningsEstimate within ±N days


@celery_app.task(
    name="worker.tasks.sentiment.llm_extraction_task.run_llm_extraction",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def run_llm_extraction(self):
    """LLM extraction pass on recent unprocessed earnings articles."""
    if not settings.llm_extraction_enabled:
        logger.debug("LLM extraction disabled — skipping")
        return {"skipped": True, "reason": "llm_extraction_disabled"}

    if not settings.anthropic_api_key:
        logger.warning("LLM extraction enabled but ANTHROPIC_API_KEY not set — skipping")
        return {"skipped": True, "reason": "no_api_key"}

    try:
        return run_async(_run_extraction_async())
    except Exception as exc:
        logger.error(f"LLM extraction task failed: {exc}")
        raise self.retry(exc=exc)


async def _run_extraction_async() -> dict:
    """Main extraction loop."""
    since = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)

    async with async_session() as session:
        result = await session.execute(
            select(Article)
            .options(selectinload(Article.article_stocks).selectinload(ArticleStock.stock))
            .where(Article.event_category == "earnings")
            .where(Article.llm_extracted.is_(None))          # not yet attempted
            .where(Article.canonical_article_id.is_(None))    # canonical only
            .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))  # no Reddit
            .where(
                (Article.quality_score >= QUALITY_THRESHOLD)
                | (Article.quality_score.is_(None))           # legacy articles without score
            )
            .where(Article.published_at >= since)
            .order_by(Article.published_at.desc())
            .limit(200)  # safety cap per run
        )
        articles = result.scalars().unique().all()

    logger.info(f"LLM extraction: {len(articles)} articles to process")

    extracted = 0
    skipped = 0
    errors = 0

    for article in articles:
        try:
            text = article.raw_text or article.summary or ""
            result = extract_earnings_context(
                title=article.title,
                article_text=text,
                max_chars=settings.llm_max_article_chars,
            )

            async with async_session() as session:
                art = await session.get(Article, article.id)
                if art is None:
                    continue

                if result is None:
                    # API call failed — mark as attempted (False) to avoid retrying
                    art.llm_extracted = False
                    errors += 1
                else:
                    guidance = result.get("guidance_change")
                    tone = result.get("management_tone")

                    # Store management tone in metadata JSONB
                    if tone:
                        meta = dict(art.metadata_ or {})
                        meta["management_tone"] = tone
                        art.metadata_ = meta

                    # Update matching EarningsEstimate if guidance was found
                    if guidance and guidance != "none":
                        await _update_earnings_guidance(session, article, guidance)

                    art.llm_extracted = True
                    extracted += 1

                await session.commit()

        except Exception as e:
            logger.error(f"Error processing article {article.id}: {e}")
            errors += 1

        time.sleep(settings.llm_rate_limit_seconds)

    logger.info(
        f"LLM extraction complete: {extracted} extracted, {skipped} skipped, {errors} errors"
    )
    return {"extracted": extracted, "skipped": skipped, "errors": errors}


async def _update_earnings_guidance(session, article: Article, guidance_change: str) -> None:
    """Find the EarningsEstimate closest to the article's publish date and update guidance_change.

    Only updates records where guidance_change is currently NULL — never overwrites.
    Matches by stock_id (via ArticleStock) and earnings_date within ±EARNINGS_MATCH_DAYS.
    """
    if not article.published_at:
        return

    pub_date = article.published_at.date() if hasattr(article.published_at, "date") else article.published_at
    window_start = pub_date - timedelta(days=EARNINGS_MATCH_DAYS)
    window_end   = pub_date + timedelta(days=EARNINGS_MATCH_DAYS)

    # Get stock_ids linked to this article
    ar_result = await session.execute(
        select(ArticleStock.stock_id).where(ArticleStock.article_id == article.id)
    )
    stock_ids = [r.stock_id for r in ar_result.all()]

    if not stock_ids:
        return

    for stock_id in stock_ids:
        # Find closest matching EarningsEstimate within the date window
        ee_result = await session.execute(
            select(EarningsEstimate)
            .where(EarningsEstimate.stock_id == stock_id)
            .where(EarningsEstimate.earnings_date >= window_start)
            .where(EarningsEstimate.earnings_date <= window_end)
            .where(EarningsEstimate.guidance_change.is_(None))   # don't overwrite
            .order_by(EarningsEstimate.earnings_date.asc())
            .limit(1)
        )
        ee = ee_result.scalar_one_or_none()

        if ee is not None:
            ee.guidance_change = guidance_change
            logger.debug(
                f"Updated guidance_change={guidance_change} on EarningsEstimate "
                f"id={ee.id} (stock_id={stock_id}, date={ee.earnings_date})"
            )
```

---

## Step 7: Update `backend/worker/celery_app.py`

Add to the `include` list:

```python
"worker.tasks.sentiment.llm_extraction_task",
```

---

## Step 8: Update `backend/worker/beat_schedule.py`

Add the extraction task at :20 (after sentiment :15, before signals :30):

```python
# LLM extraction — earnings articles only, runs only when LLM_EXTRACTION_ENABLED=true
"run-llm-extraction": {
    "task": "worker.tasks.sentiment.llm_extraction_task.run_llm_extraction",
    "schedule": crontab(minute=20),
},
```

---

## Step 9: Admin Endpoint — `backend/app/api/admin.py`

Add a manual trigger following the existing pattern:

```python
@router.post("/run-llm-extraction", status_code=202)
async def trigger_llm_extraction(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Trigger LLM extraction on recent unprocessed earnings articles."""
    from worker.tasks.sentiment.llm_extraction_task import run_llm_extraction

    task = run_llm_extraction.delay()
    await record_audit(db, current_user.id, "run_llm_extraction", "articles", None)
    return {"task_id": task.id, "status": "queued"}
```

---

## Step 10: Frontend — Admin Page

In `frontend/src/pages/AdminPage.tsx`, add one trigger button:

- **Run LLM Extraction** → `POST /api/admin/run-llm-extraction`

Note: label this button clearly as "(Requires LLM_EXTRACTION_ENABLED=true)" so the
admin knows it requires configuration. Follow the existing TaskButton pattern.

---

## Step 11: Deployment Environment Variables

On the **Compute VM** `.env` (where Celery runs), add:

```
LLM_EXTRACTION_ENABLED=true       # set to true only when ready to use
GEMINI_API_KEY=AIza...            # your Google AI Studio API key
LLM_MAX_ARTICLE_CHARS=1500
LLM_RATE_LIMIT_SECONDS=2.0        # 2s delay = ~30 req/min, safely under 15 RPM free limit
```

Get your API key from https://aistudio.google.com/app/apikey — free with a Google account.
Leave `LLM_EXTRACTION_ENABLED=false` initially. Enable only after verifying the
task runs correctly via admin trigger.

---

## Test Requirements

### New file: `backend/tests/test_llm_extraction.py`

**Tests for `extract_earnings_context` (mock `google.generativeai` client):**

| Test case | Assertion |
|---|---|
| Valid JSON response `{"guidance_change": "raised", "management_tone": "confident"}` | returns parsed dict |
| API raises exception → returns None, no crash | error handled gracefully |
| Response JSON has invalid guidance_change value → field set to None | bad values rejected |
| Response JSON has invalid management_tone value → field set to None | bad values rejected |
| `"none"` for guidance_change → returned as `"none"` (caller skips updating DB) | valid sentinel |
| Empty article text → passes empty string, no crash | empty handled |
| Text longer than max_chars → only first max_chars sent | truncation applied |
| `GEMINI_API_KEY` empty → Gemini client raises exception → returns None | no key handled |

**Tests for `run_llm_extraction` task (mock DB + mock `extract_earnings_context`):**

| Test case | Assertion |
|---|---|
| `LLM_EXTRACTION_ENABLED=false` → returns `{"skipped": True}`, no DB queries | disabled respected |
| `gemini_api_key=""` → returns skipped, no API calls | no key respected |
| Article found, extraction succeeds, guidance="raised" → EarningsEstimate updated | guidance persisted |
| Article found, management_tone="cautious" → article.metadata_["management_tone"] set | tone stored |
| EarningsEstimate already has guidance_change → NOT overwritten | no overwrite |
| `extract_earnings_context` returns None → article.llm_extracted = False | failure tracked |
| Article with no article_stocks → no EarningsEstimate lookup, still marks extracted | no stock ok |
| guidance_change = "none" → EarningsEstimate NOT updated | "none" sentinel skipped |
| Published_at = None → `_update_earnings_guidance` returns early | null date safe |

**Tests for `_update_earnings_guidance`:**

| Test case | Assertion |
|---|---|
| Article published 2 days before earnings → matches, updates guidance | within window |
| Article published 8 days before earnings (> EARNINGS_MATCH_DAYS) → no match | outside window |
| Two stocks linked to article, both have EarningsEstimate → both updated | multi-stock |

---

## Implementation Order

1. Add `anthropic` to `pyproject.toml`
2. Write migration `012_llm_extraction`
3. Update `backend/app/models/article.py` — add `llm_extracted`
4. Update `backend/app/config.py` — add new settings
5. Write `backend/worker/utils/llm_extractor.py`
6. Write unit tests for `extract_earnings_context` with mocked client — all must pass
7. Write `backend/worker/tasks/sentiment/llm_extraction_task.py`
8. Write unit tests for the task — all must pass
9. Add module to `backend/worker/celery_app.py` include list
10. Add schedule to `backend/worker/beat_schedule.py`
11. Add admin endpoint to `backend/app/api/admin.py`
12. Run `make test-unit` — all tests must pass
13. Add admin button to `AdminPage.tsx`
14. Run `make build` to verify frontend compiles

---

## Post-Deploy Steps

```bash
# Docker VM
make migrate      # applies 012_llm_extraction
make build
make up

# Compute VM
git pull origin main
# Add ANTHROPIC_API_KEY to .env (leave LLM_EXTRACTION_ENABLED=false initially)
sudo systemctl restart celery-worker celery-beat
```

After deploy, to test:
1. Keep `LLM_EXTRACTION_ENABLED=false` — verify task runs and returns `{"skipped": True}`
2. Set `LLM_EXTRACTION_ENABLED=true` in Compute VM `.env`
3. Restart Celery workers: `sudo systemctl restart celery-worker`
4. Admin → **Run LLM Extraction** — triggers immediately
5. Check Celery worker logs: look for `LLM extraction complete: N extracted`
6. Query DB: `SELECT guidance_change FROM earnings_estimates WHERE guidance_change IS NOT NULL LIMIT 10`
7. Verify articles: `SELECT metadata_ FROM articles WHERE llm_extracted = true LIMIT 5`

---

## Post-Deploy Validation Checklist

- [ ] `articles.llm_extracted` column exists
- [ ] Task returns `skipped=True` when `LLM_EXTRACTION_ENABLED=false`
- [ ] Task returns `skipped=True` when `ANTHROPIC_API_KEY` is empty
- [ ] After enabling, admin trigger processes articles and logs "LLM extraction complete"
- [ ] `earnings_estimates.guidance_change` has non-NULL values for recent earnings articles
- [ ] `articles.metadata_` contains `management_tone` for processed articles
- [ ] Next signal generation run produces non-zero `earnings_score` boost for stocks with guidance data
- [ ] `make test-unit` passes

---

## Cost Monitoring

Monitor API usage in the Google AI Studio console (https://aistudio.google.com).
With 86 tickers and quarterly earnings, expect ~344 earnings articles/year across the portfolio.
At 50 articles/day peak during earnings season: ~$0.0016/day.

The free tier (15 RPM, 1M tokens/day) covers this use case entirely — you should not
incur any charges on the AI Plus plan given the low volume.

If you ever hit rate limits (HTTP 429), increase `LLM_RATE_LIMIT_SECONDS` to 4.0 or higher.

If you want to reduce token usage further:
- Lower `LLM_MAX_ARTICLE_CHARS` from 1500 to 800
- Only process articles where `reported=True` on the matching EarningsEstimate (already done)
- Increase `QUALITY_THRESHOLD` to 0.60 to filter more aggressively
