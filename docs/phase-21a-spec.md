# Phase 21a: Data Quality Gates — Implementation Specification

> **As implemented:** Migration `008_data_quality` (`down_revision = "007"`). Adds `articles.quality_score`, `articles.canonical_article_id`, and `signals.retail_sentiment_score`. Reddit isolation stores retail sentiment separately; it is not a composite-score component.

## Overview

Four changes to the data pipeline, each independently deployable:

1. **Ticker confidence gate** — `ArticleStock.confidence >= 0.70` required for signal scoring. Company name matches (0.60) and industry keyword matches (0.45) are excluded from signals.
2. **Reddit isolation** — Reddit articles excluded from composite signal scoring. Their sentiment is tracked separately as `retail_sentiment_score`.
3. **Article quality score** — Every article gets a `quality_score` (0.0–1.0) computed at scrape time. Articles scoring < 0.40 are excluded from signal scoring.
4. **Canonical article assignment** — Within each duplicate group, the highest-quality-score article is designated canonical. Non-canonical duplicates are excluded from signal scoring.

---

## Files To Read Before Implementing

The implementing AI must read these files in full before writing any code:

- `backend/app/config.py` — for `SOURCE_CREDIBILITY`, `DEFAULT_SOURCE_CREDIBILITY`, and settings patterns
- `backend/app/models/article.py`
- `backend/app/models/signal.py`
- `backend/app/schemas/article.py`
- `backend/worker/tasks/scraping/base_scraper.py`
- `backend/worker/tasks/scraping/orchestrate.py`
- `backend/worker/tasks/signals/component_scores.py`
- `backend/worker/tasks/signals/signal_generator.py`
- `backend/app/api/admin.py`
- `backend/alembic/versions/007_infrastructure.py` — to match migration style

---

## Step 1: Database Migration `008_data_quality`

File: `backend/alembic/versions/008_data_quality.py`

```
revision = "008"
down_revision = "007"
```

### Upgrade

```sql
-- 1. Articles: quality score
ALTER TABLE articles ADD COLUMN quality_score FLOAT;
CREATE INDEX ix_articles_quality_score ON articles (quality_score);

-- 2. Articles: canonical article reference (self-referential FK)
ALTER TABLE articles ADD COLUMN canonical_article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL;
CREATE INDEX ix_articles_canonical_article_id ON articles (canonical_article_id);

-- 3. Signals: retail (Reddit-only) sentiment score
ALTER TABLE signals ADD COLUMN retail_sentiment_score FLOAT;
```

### Downgrade

```sql
DROP INDEX IF EXISTS ix_articles_canonical_article_id;
ALTER TABLE articles DROP COLUMN IF EXISTS canonical_article_id;
DROP INDEX IF EXISTS ix_articles_quality_score;
ALTER TABLE articles DROP COLUMN IF EXISTS quality_score;
ALTER TABLE signals DROP COLUMN IF EXISTS retail_sentiment_score;
```

Use `sa.Column`, `op.add_column`, `op.drop_column`, `op.create_index`, `op.drop_index` in the Alembic op style consistent with `007_infrastructure.py`. The `canonical_article_id` FK must be added using `op.create_foreign_key` after the column, not inline, to avoid circular table reference issues.

---

## Step 2: New File — `backend/worker/utils/article_quality.py`

Pure utility module with no DB or Celery dependencies.

```python
"""Article quality scoring.

Computes a 0.0–1.0 quality score for articles at scrape time.
Used to gate low-quality articles from signal scoring.
"""

import re

# ── Quality gate threshold ──
QUALITY_THRESHOLD = 0.40  # Articles below this are excluded from signal scoring

# ── Signal pipeline gates ──
SIGNAL_MIN_TICKER_CONFIDENCE = 0.70   # ArticleStock.confidence floor for signal inclusion
SIGNAL_EXCLUDED_SOURCES = frozenset({"reddit"})  # Sources excluded from composite scoring

# Regex: presence of quantitative financial content
_QUANTITATIVE_RE = re.compile(
    r"\d+\.?\d*\s*%"                                         # percentages: 12.5%
    r"|\$\s*\d+"                                             # dollar amounts: $100
    r"|\d+\.?\d*\s*(million|billion|trillion)"               # magnitude numbers
    r"|\b\d+\.?\d*\s*(bps|basis points|cents)"              # financial units
    r"|\b(EPS|revenue|earnings|profit|loss|margin|guidance)" # earnings keywords near numbers
    r"\s+(of\s+)?\$?\d+",
    re.IGNORECASE,
)


def compute_article_quality(
    source: str,
    raw_text: str | None,
    max_ticker_confidence: float,
    source_credibility_map: dict[str, float],
    default_credibility: float = 0.5,
) -> float:
    """Compute article quality score on a 0.0–1.0 scale.

    Factor weights (sum to 1.0):
      Source credibility       0.40  — from SOURCE_CREDIBILITY map in config
      Quantitative content     0.25  — presence of financial numbers/metrics
      Ticker confidence        0.25  — max ArticleStock.confidence for this article
      Article length (>=150w)  0.10  — proxy for substantive content

    Args:
        source: Article source name (e.g. "reuters", "reddit").
        raw_text: Full article text (or None if unavailable).
        max_ticker_confidence: Highest confidence of any ArticleStock association.
                               Pass 0.0 if the article has no ticker associations.
        source_credibility_map: The SOURCE_CREDIBILITY dict from app.config.
        default_credibility: Credibility to use for unknown sources.

    Returns:
        Float in [0.0, 1.0], rounded to 4 decimal places.
    """
    text = raw_text or ""

    # Factor 1: source credibility (already in [0, 1])
    credibility = source_credibility_map.get(source, default_credibility)

    # Factor 2: quantitative content
    has_quant = bool(_QUANTITATIVE_RE.search(text))
    quant_factor = 1.0 if has_quant else 0.0

    # Factor 3: ticker confidence (already in [0, 1])
    confidence_factor = min(max_ticker_confidence, 1.0)

    # Factor 4: article length
    word_count = len(text.split()) if text else 0
    length_factor = 1.0 if word_count >= 150 else 0.0

    score = (
        0.40 * credibility
        + 0.25 * quant_factor
        + 0.25 * confidence_factor
        + 0.10 * length_factor
    )

    return round(min(max(score, 0.0), 1.0), 4)
```

---

## Step 3: Modify `backend/app/models/article.py`

Add two new columns to the `Article` class. Insert after the existing `duplicate_group_id` column:

```python
quality_score: Mapped[float | None] = mapped_column(nullable=True)
canonical_article_id: Mapped[int | None] = mapped_column(
    ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True
)
```

No new relationship needed for `canonical_article_id` — it is used as a plain FK field, not a joined relationship, to avoid self-referential ORM complexity.

---

## Step 4: Modify `backend/app/models/signal.py`

Add one column to `Signal`. Insert after `ml_confidence`:

```python
retail_sentiment_score: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
```

---

## Step 5: Modify `backend/worker/tasks/scraping/base_scraper.py`

### 5a. Add imports at top of file

```python
from worker.utils.article_quality import compute_article_quality
```

Also ensure `SOURCE_CREDIBILITY` and `DEFAULT_SOURCE_CREDIBILITY` are imported from `app.config`.
Check the existing import line — if they are not already there, add them.

### 5b. Compute `quality_score` after ticker extraction

In `_store_async`, the `tickers` list is already available from the `extract_tickers()` call.
Insert the quality score computation immediately after the `ArticleStock` insertion loop
(after all article_stocks have been flushed), but before `new_count += 1`:

```python
# Compute quality score using already-extracted data
max_ticker_confidence = max((conf for _, conf in tickers), default=0.0) if tickers else 0.0
article.quality_score = compute_article_quality(
    source=self.source_name,
    raw_text=raw_text,
    max_ticker_confidence=max_ticker_confidence,
    source_credibility_map=SOURCE_CREDIBILITY,
    default_credibility=DEFAULT_SOURCE_CREDIBILITY,
)
```

No additional DB flush needed — `quality_score` will be committed with the same `session.commit()` at the end of `_store_async`.

---

## Step 6: New File — `backend/worker/tasks/scraping/article_cleanup.py`

```python
"""Post-scrape cleanup tasks.

Assigns canonical articles within duplicate groups and backfills quality scores.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from app.database import async_session
from app.models.article import Article, ArticleStock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.scraping.assign_canonical_articles",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def assign_canonical_articles(self):
    """Designate canonical articles within duplicate groups.

    Runs after all scrapers complete. Within each duplicate_group_id:
      - The article with the highest quality_score is canonical
        (its canonical_article_id is set to NULL).
      - All other members get canonical_article_id = id of the canonical article.

    Only processes articles scraped in the last 48 hours.
    """
    try:
        return run_async(_assign_canonical_async())
    except Exception as exc:
        logger.error(f"Canonical assignment failed: {exc}")
        raise self.retry(exc=exc)


async def _assign_canonical_async() -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    groups_processed = 0
    articles_updated = 0

    async with async_session() as session:
        result = await session.execute(
            select(Article.id, Article.duplicate_group_id, Article.quality_score)
            .where(Article.scraped_at >= since)
            .where(Article.duplicate_group_id.isnot(None))
            .order_by(Article.duplicate_group_id)
        )
        rows = result.all()

        if not rows:
            logger.info("Canonical assignment: no duplicate groups in last 48h")
            return {"groups_processed": 0, "articles_updated": 0}

        # Build groups: duplicate_group_id -> list of (article_id, quality_score)
        groups: dict[int, list[tuple[int, float]]] = {}
        for row in rows:
            quality = float(row.quality_score) if row.quality_score is not None else 0.5
            groups.setdefault(row.duplicate_group_id, []).append((row.id, quality))

        for group_id, members in groups.items():
            groups_processed += 1

            if len(members) == 1:
                # Single member — ensure it is marked canonical
                await session.execute(
                    update(Article)
                    .where(Article.id == members[0][0])
                    .values(canonical_article_id=None)
                )
                continue

            # Sort descending by quality; highest quality is canonical
            members.sort(key=lambda x: x[1], reverse=True)
            canonical_id = members[0][0]
            duplicate_ids = [m[0] for m in members[1:]]

            # Canonical article: clear any stale canonical_article_id
            await session.execute(
                update(Article)
                .where(Article.id == canonical_id)
                .values(canonical_article_id=None)
            )

            # Duplicate articles: point to canonical
            await session.execute(
                update(Article)
                .where(Article.id.in_(duplicate_ids))
                .values(canonical_article_id=canonical_id)
            )

            articles_updated += len(duplicate_ids)

        await session.commit()

    logger.info(
        f"Canonical assignment complete: {groups_processed} groups, "
        f"{articles_updated} articles marked as duplicates"
    )
    return {"groups_processed": groups_processed, "articles_updated": articles_updated}


@celery_app.task(
    name="worker.tasks.scraping.backfill_article_quality_scores",
    bind=True,
    max_retries=0,
)
def backfill_article_quality_scores(self):
    """Backfill quality_score for all articles where quality_score IS NULL.

    Admin-triggered. Processes in batches of 500 to avoid memory pressure.
    """
    try:
        return run_async(_backfill_quality_async())
    except Exception as exc:
        logger.error(f"Quality score backfill failed: {exc}")
        raise


async def _backfill_quality_async() -> dict:
    from app.config import DEFAULT_SOURCE_CREDIBILITY, SOURCE_CREDIBILITY
    from worker.utils.article_quality import compute_article_quality

    batch_size = 500
    total_processed = 0

    while True:
        async with async_session() as session:
            # Fetch next batch of articles missing quality_score
            result = await session.execute(
                select(Article.id, Article.source, Article.raw_text)
                .where(Article.quality_score.is_(None))
                .limit(batch_size)
            )
            articles = result.all()

            if not articles:
                break

            article_ids = [a.id for a in articles]

            # Get max ArticleStock confidence per article in this batch
            conf_result = await session.execute(
                select(
                    ArticleStock.article_id,
                    func.max(ArticleStock.confidence).label("max_conf"),
                )
                .where(ArticleStock.article_id.in_(article_ids))
                .group_by(ArticleStock.article_id)
            )
            conf_map = {row.article_id: float(row.max_conf) for row in conf_result.all()}

            for article in articles:
                max_conf = conf_map.get(article.id, 0.0)
                quality = compute_article_quality(
                    source=article.source,
                    raw_text=article.raw_text,
                    max_ticker_confidence=max_conf,
                    source_credibility_map=SOURCE_CREDIBILITY,
                    default_credibility=DEFAULT_SOURCE_CREDIBILITY,
                )
                await session.execute(
                    update(Article)
                    .where(Article.id == article.id)
                    .values(quality_score=quality)
                )

            await session.commit()
            total_processed += len(articles)
            logger.info(f"Quality backfill: {total_processed} articles processed so far")

    logger.info(f"Quality backfill complete: {total_processed} total articles")
    return {"articles_processed": total_processed}
```

---

## Step 7: Modify `backend/worker/tasks/scraping/orchestrate.py`

### 7a. Add import inside `orchestrate_scraping` function body

At the top of the function body (matching the existing pattern of local imports):

```python
from worker.tasks.scraping.article_cleanup import assign_canonical_articles
```

### 7b. Insert canonical assignment between scraping and sentiment

After `result.get(timeout=300, ...)` and the `total_new` computation, insert:

```python
# Assign canonical articles before sentiment processing
logger.info("Running canonical article assignment")
assign_canonical_articles.apply_async().get(timeout=120, disable_sync_subtasks=False)
```

The existing `if total_new > 0: process_new_articles_sentiment.delay()` line remains unchanged below it.

---

## Step 8: Modify `backend/worker/tasks/signals/component_scores.py`

### 8a. Add imports

```python
from app.models.article import Article, ArticleStock  # ArticleStock is new
from worker.utils.article_quality import (
    QUALITY_THRESHOLD,
    SIGNAL_EXCLUDED_SOURCES,
    SIGNAL_MIN_TICKER_CONFIDENCE,
)
```

(`Article` is already imported — only `ArticleStock` and the three constants are new.)

### 8b. Update `calc_sentiment_momentum`

Replace the existing query with:

```python
result = await session.execute(
    select(
        SentimentScore.positive_score,
        SentimentScore.negative_score,
        SentimentScore.processed_at,
        Article.source,
        Article.duplicate_group_id,
    )
    .join(Article, SentimentScore.article_id == Article.id)
    .join(
        ArticleStock,
        (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
    )
    .where(SentimentScore.stock_id == stock_id)
    .where(SentimentScore.processed_at >= since)
    .where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
    .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
    .where(
        (Article.quality_score >= QUALITY_THRESHOLD)
        | (Article.quality_score.is_(None))
    )
    .where(Article.canonical_article_id.is_(None))
    .order_by(SentimentScore.processed_at.desc())
)
```

**Why `quality_score IS NULL` is included:** backward compatibility for articles that predate the backfill. Once `POST /api/admin/backfill-quality-scores` has run, no NULL quality_score articles will remain.

**Why `canonical_article_id IS NULL`:** articles not part of any duplicate group also have `canonical_article_id = NULL`, so they are correctly included. Only confirmed non-canonical duplicates have a non-NULL value.

### 8c. Update `calc_sentiment_volume`

The function has two queries — 24h window and 20-day baseline. Apply the same four filters to **both**:

```python
.join(
    ArticleStock,
    (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
)
.where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
.where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
.where(
    (Article.quality_score >= QUALITY_THRESHOLD)
    | (Article.quality_score.is_(None))
)
.where(Article.canonical_article_id.is_(None))
```

Apply to both the 24h query and the 20-day baseline query so the ratio is computed on the same filtered population.

### 8d. Update `get_recent_article_count`

```python
result = await session.execute(
    select(Article.duplicate_group_id)
    .join(SentimentScore, SentimentScore.article_id == Article.id)
    .join(
        ArticleStock,
        (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
    )
    .where(SentimentScore.stock_id == stock_id)
    .where(SentimentScore.processed_at >= since)
    .where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
    .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
    .where(
        (Article.quality_score >= QUALITY_THRESHOLD)
        | (Article.quality_score.is_(None))
    )
    .where(Article.canonical_article_id.is_(None))
)
```

### 8e. Add new function `calc_retail_sentiment_score`

Append at the end of the file:

```python
async def calc_retail_sentiment_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Exponentially weighted sentiment from Reddit-only articles.

    Tracks retail investor sentiment separately from institutional signal scoring.
    Uses the same decay as calc_sentiment_momentum but with no quality gate —
    we want all retail opinion, not just high-quality articles.

    Returns value in [-1, 1] or None if no Reddit articles exist in window.
    """
    since = now - timedelta(hours=48)
    result = await session.execute(
        select(
            SentimentScore.positive_score,
            SentimentScore.negative_score,
            SentimentScore.processed_at,
        )
        .join(Article, SentimentScore.article_id == Article.id)
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
        .where(Article.source == "reddit")
    )
    rows = result.all()

    if not rows:
        return None

    decay_rate = math.log(2) / SENTIMENT_HALF_LIFE_HOURS
    weighted_sum = 0.0
    weight_total = 0.0

    for row in rows:
        sentiment_value = float(row.positive_score) - float(row.negative_score)
        hours_ago = (now - row.processed_at).total_seconds() / 3600
        weight = math.exp(-decay_rate * hours_ago)
        weighted_sum += sentiment_value * weight
        weight_total += weight

    if weight_total == 0:
        return None

    return weighted_sum / weight_total
```

---

## Step 9: Modify `backend/worker/tasks/signals/signal_generator.py`

### 9a. Add to import block

```python
from worker.tasks.signals.component_scores import (
    calc_options_score,
    calc_price_momentum,
    calc_retail_sentiment_score,   # new
    calc_rsi_score,
    calc_sentiment_momentum,
    calc_sentiment_volume,
    calc_trend_score,
    calc_volume_anomaly,
    get_recent_article_count,
)
```

### 9b. Compute retail sentiment in the per-stock loop

In `_generate_signals_async`, after `score_data = await _compute_composite_score(...)` and before constructing the `Signal` object:

```python
retail_sentiment = await calc_retail_sentiment_score(session, stock.id, now)
```

### 9c. Store on the Signal object

In the `Signal(...)` constructor call, add:

```python
retail_sentiment_score=round(retail_sentiment, 5) if retail_sentiment is not None else None,
```

---

## Step 10: Modify `backend/app/schemas/article.py`

Add two fields to `ArticleResponse`:

```python
quality_score: float | None = None
canonical_article_id: int | None = None
```

Both are nullable with defaults so existing API consumers are unaffected. The existing `model_config = {"from_attributes": True}` populates them from the ORM model automatically.

---

## Step 11: Modify `backend/app/api/admin.py`

Add two new endpoints following the exact style of existing trigger endpoints in that file:

```python
@router.post("/backfill-quality-scores", status_code=202)
async def trigger_backfill_quality_scores(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Trigger quality score backfill for all articles missing quality_score."""
    from worker.tasks.scraping.article_cleanup import backfill_article_quality_scores

    task = backfill_article_quality_scores.delay()
    await record_audit(db, current_user.id, "backfill_quality_scores", "articles", None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/assign-canonical-articles", status_code=202)
async def trigger_assign_canonical(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Manually trigger canonical article assignment for the last 48h."""
    from worker.tasks.scraping.article_cleanup import assign_canonical_articles

    task = assign_canonical_articles.delay()
    await record_audit(db, current_user.id, "assign_canonical_articles", "articles", None)
    return {"task_id": task.id, "status": "queued"}
```

Check the existing `record_audit` signature in `admin.py` and match its parameter order exactly.

---

## Step 12: Register New Task Module in Celery

In `backend/worker/celery_app.py`, find the `include` list in the Celery app config and add:

```python
"worker.tasks.scraping.article_cleanup",
```

---

## Step 13: Frontend — Admin Page

In `frontend/src/pages/AdminPage.tsx`, add two trigger buttons to the admin task triggers section:

- **Backfill Quality Scores** → `POST /api/admin/backfill-quality-scores`
- **Assign Canonical Articles** → `POST /api/admin/assign-canonical-articles`

Follow the exact pattern of existing trigger buttons (same card layout, loading state, success/error handling). Add corresponding API client calls if the project uses a typed admin API client module.

---

## Test Requirements

### New file: `backend/tests/test_article_quality.py`

| Test case | Assertion |
|---|---|
| High-credibility source, quantitative text, high confidence, long text | score > 0.85 |
| Reddit source (credibility 0.4), no quant text, no tickers, short text | score < 0.40 |
| Unknown source uses `default_credibility` | score computed with 0.5 * 0.40 factor |
| `raw_text=None` does not raise | returns valid float |
| Score is always in [0.0, 1.0] for any input | bounded |
| Regex matches "12.5%", "$500M", "revenue of $2B", "50 bps" | has_quant=True |
| Regex does NOT match "the company grew strongly" | has_quant=False |
| Length factor triggers at exactly 150 words | boundary condition |
| Score rounds to 4 decimal places | precision |

### New file: `backend/tests/test_canonical_assignment.py`

| Test case | Assertion |
|---|---|
| Group of 3 articles: highest quality_score gets `canonical_article_id=NULL` | correct canonical selected |
| Lower quality articles get `canonical_article_id` set to canonical's id | correct FK |
| Single-member group: `canonical_article_id = NULL` | no spurious assignment |
| Article with NULL quality_score treated as 0.5 during comparison | NULL handled gracefully |
| No duplicate groups in window: returns `groups_processed=0` | no-op path works |
| Group of 2 with equal quality_scores: one becomes canonical without crash | tie handled |

### Additions to existing `backend/tests/test_component_scores.py`

| Test case | Assertion |
|---|---|
| Article with confidence 0.60 excluded from `calc_sentiment_momentum` | score excludes it |
| Article with confidence 0.70 IS included | score includes it |
| Reddit article excluded from `calc_sentiment_momentum` | returns None when only reddit articles exist |
| Reddit article excluded from `calc_sentiment_volume` | same |
| Reddit article excluded from `get_recent_article_count` | count = 0 |
| `calc_retail_sentiment_score` returns float when reddit articles exist | returns value |
| `calc_retail_sentiment_score` returns None when no reddit articles | None |
| Non-canonical article (`canonical_article_id IS NOT NULL`) excluded from sentiment_momentum | excluded |
| Article with `quality_score < 0.40` excluded from sentiment_momentum | excluded |
| Article with `quality_score = NULL` IS included (backward compat) | included |

---

## Implementation Order

Execute in this exact sequence. Each step is a safe checkpoint before the next.

1. Write and run migration `008_data_quality` — verify with `\d articles` and `\d signals` in psql
2. Write `backend/worker/utils/article_quality.py`
3. Write and run `backend/tests/test_article_quality.py` — all must pass before continuing
4. Update `backend/app/models/article.py` — add `quality_score` and `canonical_article_id`
5. Update `backend/app/models/signal.py` — add `retail_sentiment_score`
6. Update `backend/worker/tasks/scraping/base_scraper.py` — compute quality_score at scrape time
7. Write `backend/worker/tasks/scraping/article_cleanup.py`
8. Write and run `backend/tests/test_canonical_assignment.py` — all must pass before continuing
9. Update `backend/worker/tasks/scraping/orchestrate.py` — add canonical assignment step
10. Update `backend/worker/celery_app.py` — add `article_cleanup` to include list
11. Update `backend/worker/tasks/signals/component_scores.py` — all four filters + new `calc_retail_sentiment_score`
12. Run existing + new component_score tests — all must pass
13. Update `backend/worker/tasks/signals/signal_generator.py` — compute and store `retail_sentiment_score`
14. Update `backend/app/schemas/article.py` — add `quality_score` and `canonical_article_id` fields
15. Update `backend/app/api/admin.py` — two new endpoints
16. Run full unit test suite: `make test-unit` — must pass with coverage >= 60%
17. Add admin UI buttons in `frontend/src/pages/AdminPage.tsx`
18. Deploy, then immediately run via admin UI:
    - **Backfill Quality Scores** (populates `quality_score` on all existing articles)
    - **Assign Canonical Articles** (marks existing duplicate groups)

---

## Post-Deploy Validation Checklist

- [ ] `articles.quality_score` is non-NULL on newly scraped articles
- [ ] Reddit articles still appear in the articles list UI (stored, just excluded from signals)
- [ ] `signals.retail_sentiment_score` is populated on newly generated signals for tickers with Reddit coverage
- [ ] Articles within duplicate groups have `canonical_article_id` set; the canonical article has `canonical_article_id = NULL`
- [ ] Signal `article_count` drops for tickers with heavy industry-keyword false positives (e.g. XOM, JPM receiving unrelated macro articles)
- [ ] No regression in signal generation throughput — monitor Celery task duration; the extra JOIN adds latency
- [ ] `make test-unit` passes
