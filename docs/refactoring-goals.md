# Refactoring Goals

Code quality audit findings and prioritized refactoring targets for the stock-predictor codebase.

## Backend Large Files

| File | Lines | Severity |
|------|-------|----------|
| `worker/utils/backtester.py` | 949 | CRITICAL |
| `worker/tasks/signals/signal_generator.py` | 595 | HIGH |
| `app/api/signals.py` | 495 | HIGH |
| `app/api/backtests.py` | 302 | MEDIUM |
| `app/api/alerts.py` | 260 | MEDIUM |

## Frontend Large Files

| File | Lines | Severity |
|------|-------|----------|
| `pages/StockDetailPage.tsx` | 320 | HIGH |
| `pages/SignalsPage.tsx` | 314 | HIGH |
| `pages/DashboardPage.tsx` | 206 | MEDIUM |

## Duplicated Patterns

### Card CSS (49+ instances)
`bg-white dark:bg-gray-800 rounded-xl shadow` is inlined ~49 times despite a reusable `<Card>` component existing. Migrate inline card styling to `<Card>`.

### Loading/Error States (20+ queries)
Every page manually implements `isLoading ? <Skeleton> : isError ? <Error> : <Content>` ternary chains. No centralized query wrapper exists.

### Pagination Boilerplate (7 endpoints, ~245 lines)
Identical `offset/limit` + `PaginationMeta` construction repeated across 7 API files. Create a shared pagination dependency/helper.

### Celery Task Boilerplate (19/24 tasks, 79%)
`@celery_app.task(bind=True) + run_async() + try/except/retry` pattern repeated in 19 of 24 tasks. Create a decorator factory.

## Prioritized Refactor List

### Quick Wins (1-3)
1. **Migrate inline card styling to `<Card>` component** — refactor 40+ instances of duplicated card classes
2. **Create `useQuerySection()` hook** — centralizes loading/error/empty state rendering for data queries
3. **Create Celery task decorator factory** — reduces boilerplate in 19 task definitions by ~30%

### Medium Effort (4-7)
4. **Extract pagination helper** — shared FastAPI dependency for offset/limit/meta across 7 endpoints
5. **Split `StockDetailPage.tsx` (320 lines)** — extract PriceChartSection, SentimentSection, SignalHistorySection
6. **Split `SignalsPage.tsx` (314 lines)** — extract SignalFilters, AccuracyTab, MethodologyTab
7. **Split `signal_generator.py` (595 lines)** — extract component scoring functions into separate module

### Larger Refactors (8-10)
8. **Split `backtester.py` (949 lines)** — into trade execution, metrics, signals, and benchmark modules
9. **Split `signals.py` API (495 lines)** — separate accuracy/methodology endpoints from signal CRUD
10. **Split `frontend/src/types/index.ts` (303 lines)** — into domain/, api/, backtest/ type modules

## Status

| # | Refactor | Status |
|---|----------|--------|
| 1 | Card component migration | **Done** |
| 2 | useQuerySection hook | **Done** |
| 3 | Celery decorator factory | **Done** |
| 4 | Pagination helper | **Done** |
| 5 | StockDetailPage split | **Done** |
| 6 | SignalsPage split | **Done** |
| 7 | signal_generator split | **Done** |
| 8 | backtester.py split | **Done** |
| 9 | signals.py API split | **Done** |
| 10 | types/index.ts split | **Done** |
