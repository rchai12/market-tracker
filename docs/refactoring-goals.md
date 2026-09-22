# Refactoring Goals

Code quality audit findings and prioritized refactoring targets for the stock-predictor codebase.

## Original 10-Item Refactor (Phase 8 — all complete)

The initial code quality pass identified 10 items. All are done.

| # | Refactor | Status |
|---|----------|--------|
| 1 | Card component migration (49+ inline card CSS instances → `<Card>`) | **Done** |
| 2 | `useQuerySection()` / `QueryGuard` hook (centralized loading/error/empty state) | **Done** |
| 3 | Celery task decorator factory (`@async_task`) | **Done** |
| 4 | Pagination helper (`PaginationParams`, `PaginationMeta`, `calc_total_pages()`) | **Done** |
| 5 | Split `StockDetailPage.tsx` → section components | **Done** |
| 6 | Split `SignalsPage.tsx` → `SignalsTab`, `AccuracyTab`, `MethodologyTab` | **Done** |
| 7 | Split `signal_generator.py` → `component_scores.py`, `alert_dispatcher.py`, etc. | **Done** |
| 8 | Split `backtester.py` → `backtester/` package (trade execution, metrics, signals, benchmark) | **Done** |
| 9 | Split `signals.py` API → paginated signals, accuracy/trend/distribution, weights, daily views | **Done** |
| 10 | Split `frontend/src/types/index.ts` → domain type modules | **Done** |

---

## Post-Phase-20 SSOT Refactors (all complete)

After Phase 20, several canonical shared modules were introduced to prevent formula drift
between the live signal pipeline and the backtester. All are done.

| Module | Purpose | Consumers |
|--------|---------|-----------|
| `worker/utils/signal_formula.py` | Canonical weights, regime multiplier, ML gating, signal classification | `signal_generator`, `backtester` |
| `worker/utils/component_math.py` | Pure scorers: price momentum, volume anomaly, RSI, trend, sentiment decay | `component_scores` (live, queries DB then calls), `backtester` (passes arrays) |
| `worker/utils/market_data_queries.py` | Daily close lookups: on-or-before, nth session, latest, recent series | outcome evaluator, paper portfolio, portfolio API, component scorers |
| `worker/utils/learning_queries.py` | 1-day daily-view outcome query + signals-for-views grouping | weight optimizer, ML trainer task |
| `worker/utils/performance_metrics.py` | Sharpe ratio, max drawdown, Jensen alpha/beta (rf = 0) | paper portfolio task, backtester metrics module |
| `worker/utils/daily_aggregation.py` | Net-view score/conviction, trading-date assignment, 4-hour ET buckets, recency weights (λ=0.15), sector ETF map, proportional credit | signal generator, outcome evaluator |

**Principle:** when a calculation appears in two places, one of those places is wrong.
These modules are the single sources of truth. New code must import from them, not copy.

---

## Current Refactoring Backlog

### Pass 1 — Correctness and Security (do first)

These are bugs or gaps that are small in scope but high in impact. Structural splits should
wait until these are resolved, because splitting code around an unfixed bug moves the bug to
a harder-to-find location.

| ID | File | Issue | Action |
|----|------|-------|--------|
| B1 | `app/api/admin.py` (reset-learning-layer handler) | Does not truncate `daily_signal_view_outcomes`; learning reset is incomplete | Add `daily_signal_view_outcomes` to the truncation list |
| B2 | `worker/tasks/signals/weight_optimizer.py` | `signals:weights:v2` Redis cache key not invalidated after weights are written | Call `invalidate_pattern("signals:weights*")` at the end of the optimizer task |
| B3 | `worker/tasks/signals/signal_generator.py` | No weekday gate; signals are generated on Saturdays and Sundays when market data is stale | Add `if datetime.now(timezone.utc).weekday() >= 5: return` at task entry |
| S1 | `app/api/health.py` | Error branch returns `str(exc)` which may contain DB/Redis connection strings with credentials | Replace with a generic `"check failed"` message; log the real exception server-side |
| S2 | `app/api/admin.py` (task-failures retry endpoint) | `send_task(task_failure.task_name, ...)` has no allowlist; admin can queue arbitrary task names | Add an allowlist of known Celery task paths and reject anything not on the list |

### Pass 2 — Shared Helper Adoption

These are drift risks: the canonical module exists, but some call sites still have their own
copy of the same logic. The risk is that a fix to the canonical module does not reach all
consumers.

| ID | Issue | Canonical Module | Affected Files |
|----|-------|-----------------|---------------|
| D1 | Close-price queries duplicated in 4+ places despite `market_data_queries.py` | `worker/utils/market_data_queries.py` | Any file that directly queries `market_data` for a closing price outside the SSOT |
| D2 | Learning loaders (1-day conviction query + signals-for-views grouping) duplicated between weight optimizer and ML trainer task | `worker/utils/learning_queries.py` | `weight_optimizer.py`, `ml_trainer_task.py` |
| D3 | `get_db` session factory defined in both `database.py` and `dependencies.py` | `app/dependencies.py` | Remove the duplicate in `database.py`; all imports use `dependencies.get_db` |
| D4 | Strength rank map in 3 places (`STRENGTH_ORDER`, `STRENGTH_RANK`, inline dict) | Consolidate into `worker/utils/signal_formula.py` or `app/core/constants.py` | `signal_formula.py`, `signals.py` API, frontend `constants/` |
| D5 | `@async_task` decorator adoption incomplete; most tasks still hand-roll `run_async()` + try/except/retry | `worker/utils/celery_helpers.py` | Most task modules under `worker/tasks/` |

### Pass 3 — Structural Splits (defer until Pass 1 is done)

These are real structural improvements, but they should wait. Splitting files around an
unfixed bug or under-adopted shared helper just makes subsequent fixes harder to locate.

| ID | Item | Current State | Why Defer |
|----|------|--------------|-----------|
| T1 | Split `signal_generator.py` (~558 lines) | Mixes Celery entry point, ML inference, DB persistence, reasoning text, and the weekday gate | B3 (weekday gate) lives here; fix it before splitting so the fix lands in a stable location |
| T2 | Batch N+1 queries in signal generation | ~910 DB queries per :30 run (~10 per ticker × 91 tickers); most are individual lookups that could be batched | Needs T1 split to organize batching logic cleanly without creating a 700-line function |
| T3 | Chain outcomes → weights → ML as a Celery chain | Currently three clock-offset beat entries (`:45`, `4:00 AM`, `4:30 AM`) with no guarantee of ordering | Needs D2 (learning loaders) to be clean first so the chain glue doesn't re-duplicate loader code |

---

## Principles

**Bugs before splits.** Refactoring should make the codebase easier to reason about, not
harder. Splitting a file that contains an unfixed bug moves the bug somewhere harder to find.
Fix correctness issues in Pass 1, reduce drift risk in Pass 2, then split in Pass 3.

**SSOTs must be enforced at review.** The shared modules (`signal_formula.py`,
`component_math.py`, `market_data_queries.py`, `learning_queries.py`,
`performance_metrics.py`, `daily_aggregation.py`) exist because formula drift was a real
problem. Any PR that introduces a new copy of a formula owned by one of these modules should
be rejected in review.

**`@async_task` is the standard.** New Celery tasks must use the `@async_task` decorator
from `worker/utils/celery_helpers.py`. Hand-rolled `run_async()` + try/except in task body
should be migrated when the file is already being touched.
