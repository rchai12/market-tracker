# Future Features

Context document for planned features and improvements. Each section captures the motivation,
rough approach, and key decisions to make before implementation.

## Completed Phases

| Phase | Focus | Key Deliverables |
|-------|-------|-----------------|
| 1–7 | Core platform | FastAPI backend, React frontend, scraping pipeline, FinBERT sentiment, signal generation, alerts, charts, watchlists |
| 8 | Hardening + deployment | Docker hardening, Nginx SSL, security headers, Oracle Cloud deployment |
| 9 | Data retention + optimization | Performance indexes, article compression, log cleanup, materialized views, admin endpoints |
| 10 | Signal feedback loop | Outcome evaluation (1/3/5-day windows), adaptive per-sector weight optimization, accuracy UI |
| 11 | Technical indicators | RSI, SMA, EMA, MACD, Bollinger Bands in signal scoring + frontend chart overlays/sub-charts |
| 12 | Backtesting engine | Historical signal replay, equity curves, trade logs, Sharpe/drawdown/win rate metrics |
| 13 | UX polish | Stock search, profile/password management, mobile responsive sidebar, code splitting, admin dashboard |
| 14 | Realistic backtesting | Transaction costs, position sizing, stop-loss/take-profit, benchmark comparison, CSV export |
| 15 | Signal intelligence | Component breakdown, accuracy analytics (trend/distribution), signal detail panel, methodology tab |
| 16 | Enhanced news intelligence | Event classification (10 categories), fuzzy duplicate detection, source credibility weighting |
| 17 | ML signal ensemble | LightGBM binary classifier per-sector, A/B comparison with rule-based, admin training trigger, ML accuracy dashboard |
| 18 | Options flow | yfinance options chain data, CBOE P/C ratio, 7th signal component (options score), P/C ratio & IV skew display |
| 19 | Infrastructure | Redis caching (6 endpoints), dead letter queue, API key auth, admin audit logging, health alerts (Discord), slow query detection |
| 20 | Comprehensive testing | Coverage reporting, mutation tests (3 tiers, ~138 tests), integration test suite (37 tests), E2E tests (Playwright), Vitest config |
| 21a | Data quality gates | Ticker confidence floor, Reddit signal isolation, article quality score (0–1), canonical article deduplication |
| 21b | Earnings surprise component | yfinance EPS beat/miss data, tanh(surprise_pct/5.0) scoring, 48h gate, earnings_score on signals |
| 21c | Signal formula refactor | RSI/trend repurposed as regime multiplier (±15%); base weights rebalanced to sm=40%/sv=25%/pm=20%/va=15%; market_regime label on every signal |
| 21d | LLM extraction (earnings) | Claude Haiku extracts guidance_change + management_tone from earnings articles; every 2h at :20; anthropic SDK |
| 21e | LLM quality gate | quality_score ≥ 0.60 gate for LLM extraction; reduced to every-2h frequency |
| 21f | LLM extraction (analyst) | Claude Haiku extracts rating_change, price_target, analyst_firm from analyst_rating articles → article.metadata_ JSONB |
| 21g | LLM data wired into scoring | management_tone ±0.10 modifier on earnings_score; analyst_score as gated 8th component (0.07 weight) |
| 22a | Live paper portfolio | 4 tables (portfolios/positions/trades/snapshots), :35 position management, 21:30 UTC SPY snapshot, 5 API endpoints, /portfolio page |
| 22b | Adaptive feedback upgrade | Return-weighted component votes (abs(price_change_pct) scaled by bucketed share), analyst_score in optimizer, per-(sector, regime) weights with fallback chain |
| 23a | ML ensemble promotion | ml_score gated into live composite as 8% component when validation_accuracy ≥ 55% and training_samples ≥ 50; has_ml stored on signal |
| 23b | Insider Form 4 signal | yfinance Form 4 scraper, insider_transactions table, gated 8% insider_score (role-weighted, sells at 40%), stock-detail insider section |
| 24 | Daily signal aggregation | daily_signal_views table, trading_date on signals, learning loop reads 1-day daily-view outcomes (conviction ≥ 0.20), Today's Predictions dashboard primary panel |
| 24b | Outcome quality + bucketing | Excess return vs sector ETF for is_correct (absolute for Market ETFs), 4-hour ET time buckets (pre_market/morning/afternoon), recency weighting λ=0.15 toward session close |

---

## What's Next

### Phase 24c: Daily View Accuracy Observability

**Motivation:** With daily views now scored on excess return, the Accuracy tab still shows
per-signal is_correct counts. Users cannot see how well bucketed predictions perform over
time or how conviction calibrates against actual outcomes.

**Approach:**
- Conviction calibration chart: bucket daily views by conviction decile, plot actual win rate
- Sector accuracy table: per-sector win rate + avg excess return from daily-view outcomes
- Accuracy tab update: replace or supplement per-signal accuracy with daily-view accuracy
- New endpoint: `GET /api/signals/daily-views/accuracy` — aggregated is_correct by sector/regime/period

**Key decisions:**
- Minimum sample threshold before showing a sector row (avoid misleading low-n stats)
- Whether to retire the per-signal accuracy tab entirely or keep both

---

### Pending Correctness Fixes (Pass 1 — do before structural refactors)

These are bugs or security gaps that are small in scope but high in impact. They should be
addressed before any structural refactoring that might reshuffle code around an unfixed bug.

| ID | Issue | Impact |
|----|-------|--------|
| B1 | `reset-learning-layer` does not truncate `daily_signal_view_outcomes` | Learning layer reset is incomplete; stale outcomes survive |
| B2 | `signals:weights:v2` Redis key not invalidated after weight optimizer runs | Methodology tab shows stale weights until TTL expires |
| B3 | Signal generation task has no weekday gate | Signals generated on Saturdays/Sundays with no market data |
| S1 | `/api/health` leaks `str(exc)` containing DB/Redis credentials in error responses | Credential exposure on health endpoint errors |
| S2 | DLQ retry (`/api/admin/task-failures/{id}/retry`) has no task_name allowlist | Admin can re-queue arbitrary task strings |

---

### Pending Deduplication Fixes (Pass 2 — shared helpers)

These are cases where a canonical shared module exists but call sites still have their own
copy of the same logic. They introduce drift risk (fix in one place, forget the others).

| ID | Issue | Canonical Module |
|----|-------|-----------------|
| D1 | Close-price queries still duplicated in 4+ places | `worker/utils/market_data_queries.py` |
| D2 | Learning loaders duplicated between weight_optimizer and ml_trainer_task | `worker/utils/learning_queries.py` |
| D3 | `get_db` defined in both `database.py` and `dependencies.py` | `app/dependencies.py` |
| D4 | Strength rank map in 3 places (STRENGTH_ORDER, STRENGTH_RANK, inline dict) | Consolidate into `app/core/constants.py` or `worker/utils/signal_formula.py` |
| D5 | `@async_task` decorator adoption incomplete (most tasks still hand-roll `run_async`) | `worker/utils/celery_helpers.py` |

---

### Deferred Structural Refactors (Pass 3)

These are real improvements but should be deferred until Pass 1 bugs are fixed and Pass 2
drift is reduced. Splitting files around an unfixed bug or duplicated helper makes the fix
harder, not easier.

| ID | Item | Reason to defer |
|----|------|----------------|
| T1 | Split `signal_generator.py` (558 lines) into Celery entry / ML inference / persist / reasoning modules | B3 (weekend gate) lives here; fix first |
| T2 | Batch N+1 queries in signal generation (~910 queries per :30 run, ~10 per ticker × 91 tickers) | Needs T1 split to organize batching cleanly |
| T3 | Chain outcomes → weights → ML as a Celery chain rather than clock-offset beat entries | Requires D2 cleanup to avoid duplicating loader logic in chain glue |

---

## Deferred Feature Candidates

### Real-time Data Streaming

> **Not viable on current Oracle Cloud free-tier infrastructure.** Persistent WebSocket
connections for 91 tickers would create constant network load (vs current bursty hourly
batch), competing with the Compute VM's 2 ARM cores already running Celery + FinBERT.
Free-tier bandwidth throttling and egress limits make real-time streaming impractical.
A middle ground (reducing batch interval to 15–30 min) would work within existing
constraints without architectural changes.

**Approach (if infrastructure improves):**
- WebSocket connections for live price updates (replace hourly yfinance polling)
- Server-sent events (SSE) or WebSocket push for live signal/alert delivery to frontend
- Streaming sentiment processing (process articles immediately on scrape rather than batched)

### Multi-timeframe Analysis

**Motivation:** Current signals use a single daily timeframe. Different timeframes can provide
confluence signals.

**Approach:**
- Compute indicators across multiple timeframes (daily, weekly, monthly)
- Add timeframe confluence scoring: signals that agree across timeframes are stronger
- Frontend: multi-timeframe indicator view, confluence indicator on signal cards

**Key decisions:**
- Which timeframes to support (intraday requires real-time data)
- How to weight timeframe confluence in composite score
- Whether this replaces or augments the current single-timeframe approach

### Social Sentiment Integration

> **Deprioritized due to signal noise.** Social platforms (StockTwits, Twitter/X) are
heavily polluted by bots, spam, and pump-and-dump campaigns. Twitter/X API is $100/month
minimum for read access. StockTwits is free but noisy — user-tagged sentiment is
unreliable compared to FinBERT on curated news. Adding low-quality social data risks
degrading signal accuracy rather than improving it. Reddit (already scraped, filtered by
score >= 10, isolated into retail_sentiment_score) provides the best signal-to-noise ratio
for retail sentiment without contaminating the main composite.

### Improved Frontend UX

**Motivation:** Polish and extend the dashboard for power users.

**Approach:**
- **Customizable dashboard**: Drag-and-drop widget layout, saved layouts per user
- **Chart drawing tools**: Support lines, Fibonacci, annotations on TradingView charts
- **Comparison mode**: Overlay multiple tickers on the same chart
- **Alert notifications in-app**: Toast/bell notifications, not just Discord/email
- **Keyboard shortcuts**: Power-user navigation (j/k for next/prev stock, etc.)

## Infrastructure Notes

### Performance
- Database connection pooling tuning under load
- CDN for static frontend assets

### Reliability
- Database replication (read replica for heavy queries) — not feasible on free-tier
- Worker autoscaling based on queue depth — only 2 ARM cores, no headroom

### Observability
- Prometheus metrics export (request latency, task duration, queue depth) — too heavy for free-tier
- Grafana dashboards for system monitoring — too heavy for free-tier
- Distributed tracing (OpenTelemetry) across API → Celery → DB — overkill for 2-VM setup
- Error tracking (Sentry integration) — structured logs + dead letter queue covers the gap

### Security
- OAuth2 social login (Google, GitHub) — complex UX, low ROI
- Two-factor authentication — complex UX, low ROI
