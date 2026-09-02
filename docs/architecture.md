# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Docker VM                           │
│                                                          │
│  ┌──────────┐  ┌───────┐  ┌─────────┐  ┌────────────┐  │
│  │ Postgres │  │ Redis │  │ FastAPI │  │  React App │  │
│  │   :5432  │  │ :6379 │  │  :8000  │  │    :80     │  │
│  └────┬─────┘  └───┬───┘  └────┬────┘  └─────┬──────┘  │
│       │            │           │              │          │
│       └────────────┴───────────┴──────────────┘          │
│                        │                                 │
│                   ┌────┴────┐                            │
│                   │  Nginx  │ :80/:443 (public)          │
│                   └─────────┘                            │
└─────────────────────────────────────────────────────────┘
                         │
              Oracle VPC Internal Network
                         │
┌─────────────────────────────────────────────────────────┐
│                     Compute VM                           │
│                  (2 cores, 12GB RAM)                     │
│                                                          │
│  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │    Celery Worker      │  │     Celery Beat        │   │
│  │  (concurrency=2)      │  │   (task scheduler)     │   │
│  │                        │  │                        │   │
│  │  Queues:               │  │  Schedules:            │   │
│  │  - scraping            │  │  - */5 health check    │   │
│  │  - sentiment           │  │  - :00 scrape all      │   │
│  │  - signals             │  │  - :05 market data     │   │
│  │  - maintenance         │  │  - :15 sentiment       │   │
│  │  - default             │  │  - :30 gen signals     │   │
│  │                        │  │  - :35 matview refresh │   │
│  │                        │  │  - :45 eval outcomes   │   │
│  │                        │  │  - 3AM maintenance     │   │
│  │                        │  │  - 4AM adapt weights   │   │
│  │                        │  │  - 4:30AM ML training  │   │
│  └──────────────────────┘  └────────────────────────┘   │
│                                                          │
│  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │   FinBERT Model      │  │  LightGBM Models       │   │
│  │   (~1.5GB in memory) │  │  (~50KB per sector)    │   │
│  └──────────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

```
                    External Sources
                    ┌─────────────┐
                    │ Yahoo News  │
                    │ Finviz      │
                    │ Reuters RSS │
                    │ SEC EDGAR   │
                    │ MarketWatch │
                    │ Reddit      │
                    │ FRED        │
                    │ yfinance    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Scrapers   │  (Celery tasks on Compute VM)
                    │  (hourly)   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Ticker    │  $TICKER (0.95), (TICKER) (0.90),
                    │ Extraction  │  ALL-CAPS (0.70), company name (0.60),
                    │ + Industry  │  industry keywords (0.45)
                    │  Matching   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Event     │  10 categories (earnings, M&A, etc.)
                    │ Classifier  │  + fuzzy dedup (rapidfuzz)
                    │ + Dedup     │  + source credibility scoring
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───┐ ┌──────▼──────┐
       │  Articles   │ │Stocks│ │ Market Data │  (Postgres on Docker VM)
       │  (raw text) │ │      │ │  (OHLCV)   │
       └──────┬──────┘ └──────┘ └──────┬──────┘
              │                        │
       ┌──────▼──────┐                 │
       │  FinBERT    │                 │
       │ Sentiment   │                 │
       └──────┬──────┘                 │
              │                        │
       ┌──────▼──────┐                 │
       │  Sentiment  │                 │
       │   Scores    │                 │
       └──────┬──────┘                 │
              │                        │
              └───────────┬────────────┘
                          │
                   ┌──────▼──────┐
                   │   Signal    │  (+ ML inference via LightGBM
                   │  Generator  │   if ML_ENSEMBLE_ENABLED)
                   └──────┬──────┘
                          │
              ┌───────────┼───────────┐
              │                       │
       ┌──────▼──────┐        ┌──────▼──────┐
       │  Signals    │        │   Alerts    │
       │  (stored)   │        │ (Discord +  │
       │             │        │   Email)    │
       └──────┬──────┘        └─────────────┘
              │
       ┌──────▼──────┐
       │  Outcome    │  (evaluate after 1/3/5 days)
       │  Evaluator  │
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │  Adaptive   │  (re-weight components daily)
       │  Weights    │──── feeds back to Signal Generator
       └──────┬──────┘
              │
       ┌──────▼──────┐
       │  React App  │
       │ (Dashboard, │
       │  Charts,    │
       │  Indicators,│
       │  Accuracy,  │
       │  Backtest,  │
       │  Signal     │
       │  Intel)     │
       └─────────────┘
```

## Database Schema

### Entity Relationships

```
users ──< watchlist_items >── stocks
users ──< alert_configs
users ──< backtests
users ──< api_keys
stocks ──< article_stocks >── articles
stocks ──< market_data_daily
stocks ──< market_data_intraday
articles ──< sentiment_scores
stocks ──< signals
signals ──< alert_logs
signals ──< signal_outcomes
stocks >── sectors
sectors ──< signal_weights
sectors ──< ml_models
backtests ──< backtest_trades
backtests >── stocks (nullable)
backtests >── sectors (nullable)
```

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| users | Authentication and preferences | email, username, password_hash, discord_webhook_url |
| sectors | Stock groupings (Energy, Financials, Technology, ...) | name, is_active |
| stocks | S&P 500 tickers | ticker, company_name, sector_id, industry, is_active |
| market_data_daily | Historical OHLCV | stock_id, date, open/high/low/close/volume |
| market_data_intraday | Intraday prices | stock_id, timestamp, OHLCV |
| articles | Scraped news/filings | source, source_url, title, raw_text, is_processed, event_category, duplicate_group_id |
| article_stocks | Article-to-ticker mapping | article_id, stock_id, confidence |
| sentiment_scores | FinBERT analysis results | article_id, stock_id, label, positive/negative/neutral scores |
| signals | Composite trading signals | stock_id, direction, strength, composite_score, sentiment_volume_score, rsi_score, trend_score, reasoning, ml_score, ml_direction, ml_confidence |
| signal_outcomes | Signal accuracy evaluation | signal_id, window_days, is_correct, price_change_pct |
| signal_weights | Adaptive component weights (per-sector) | sector_id, sentiment_momentum, rsi, trend, accuracy_pct |
| alert_configs | User alert preferences | user_id, stock_id, min_strength, channel |
| alert_logs | Sent alert history | signal_id, user_id, channel, success |
| watchlist_items | User watchlists | user_id, stock_id |
| scrape_logs | Scraper execution logs | source, articles_found, articles_new, errors |
| backtests | Backtest run configurations and results | user_id, stock_id/sector_id, mode, status, metrics, equity_curve (JSON), commission/slippage/position_size/stop_loss/take_profit, benchmark_ticker, benchmark metrics (alpha/beta), benchmark_equity_curve (JSON) |
| backtest_trades | Individual trades within a backtest | backtest_id, ticker, action, price, shares, signal_score, return_pct, exit_reason |
| ml_models | ML model registry (one active per sector) | sector_id, model_version, training_samples, validation_accuracy, validation_f1, model_path, feature_importances |
| task_failures | Dead letter queue for failed Celery tasks | task_name, task_args, exception_type, exception_message, traceback, failed_at, retried_at |
| api_keys | API key authentication (per-user) | user_id, key_hash (SHA-256), key_prefix, name, is_active, last_used_at, expires_at |
| audit_logs | Admin action audit trail | user_id, action, resource, detail (JSON), ip_address, created_at |
| options_activity | Daily per-ticker options aggregates | stock_id, date, put_call_ratio, iv_skew, volume/OI, data_quality |
| cboe_put_call_ratio | Market-wide CBOE put/call ratio | date, put_call_ratio, equity_pc_ratio |
| earnings_estimates | Consensus vs actual EPS per ticker/quarter | stock_id, earnings_date, eps_estimate, eps_actual, surprise_pct, guidance_change |

## Signal Scoring Algorithm

Live scoring and backtests share `worker/utils/signal_formula.py` (`combine_component_scores`) so they cannot drift.

Four predictive components, plus gated earnings/options. RSI and trend are **not** additive — they apply a regime multiplier to the composite.

```
raw = 0.40 * sentiment_momentum + 0.25 * sentiment_volume
    + 0.20 * price_momentum    + 0.15 * volume_anomaly
    + 0.10 * earnings_score   (when a report is within 48h; other weights scale down)
    + 0.08 * options_score    (when OPTIONS_FLOW_ENABLED; other weights scale down)

composite, market_regime = apply_regime_multiplier(raw, rsi_score, trend_score)
```

| Component | Default weight | Description | Range |
|-----------|----------------|-------------|-------|
| sentiment_momentum | 0.40 | Exponentially weighted avg of sentiment scores (half-life 6h) | [-1, 1] |
| sentiment_volume | 0.25 | Article count vs 20-day baseline, signed by net sentiment | [-1, 1] |
| price_momentum | 0.20 | 5-day price change, tanh scaled | [-1, 1] |
| volume_anomaly | 0.15 | Trading volume vs 20-day avg, signed by price direction | [-1, 1] |
| earnings_score | 0.10 (gated) | EPS beat/miss vs consensus; active only within 48h of report | [-1, 1] |
| options_score | 0.08 (gated) | P/C ratio + IV skew z-scores vs 20-day baseline | [-1, 1] |
| rsi_score | regime only | RSI(14) mapped to [-1,1]; extreme → dampen composite 15% | [-1, 1] |
| trend_score | regime only | 60% SMA crossover + 40% MACD; confirm ×1.15 / oppose ×0.85 | [-1, 1] |

**Regime multiplier:** `|rsi| > 0.4` → overbought/oversold (×0.85). Else `|trend| > 0.3` confirming → ×1.15, opposing → ×0.85. Otherwise sideways (×1.0).

**Thresholds:**
- Strong: |composite| > 0.6
- Moderate: |composite| > 0.35
- Weak: everything else

### Adaptive Weights

Default weights are overridden by per-sector adaptive weights computed daily at 4 AM. The weight optimizer analyzes signal outcomes (1/3/5-day windows) to determine which components are most predictive for each sector, then rebalances weights accordingly. Weights are clamped to configurable min/max bounds and normalized to sum to 1.0.

### Technical Indicators

All indicators are computed on-the-fly from stored OHLCV data (no extra DB tables):

| Indicator | Parameters | Purpose |
|-----------|-----------|---------|
| SMA | 20-period, 50-period | Moving average overlays, trend direction |
| EMA | Configurable period | MACD calculation building block |
| RSI | 14-period (Wilder's) | Overbought/oversold detection for signal scoring |
| MACD | Fast=12, Slow=26, Signal=9 | Trend momentum for signal scoring and charting |
| Bollinger Bands | 20-period, 2 std deviations | Volatility visualization on price chart |

## Historical Data Initialization

On first setup, `scripts/seed_historical_data.py` backfills the full available price history for all active tickers via yfinance (`period="max"`). This provides ~30+ years of daily OHLCV data per ticker (~7,500 rows each, ~340K total rows, ~50MB in Postgres).

This ensures the signal algorithm has deep historical baselines (20-day moving averages for price momentum and volume anomaly) from day one, rather than starting blind and needing weeks to accumulate enough data.

The historical seed is idempotent (upserts via `ON CONFLICT DO UPDATE`) and skips tickers that already have 5,000+ rows.

## Sentiment Analysis Pipeline

FinBERT (ProsusAI/finbert) runs as a singleton on the Compute VM, lazy-loaded on first use to avoid startup overhead.

**Flow:**
1. Scraper orchestration completes → automatically chains `process_new_articles_sentiment`
2. Task queries all articles where `is_processed = false` with eager-loaded `article_stocks`
3. For each article, selects best text source: `raw_text` → `summary` → `title`
4. FinBERT analyzes text (chunking at ~2048 chars for long articles, averaging scores across chunks)
5. Stores `SentimentScore` per article-stock pair (or `stock_id=NULL` for unlinked articles)
6. Marks article as `is_processed = true`

**Configuration (via pydantic-settings):**
- `finbert_model_path`: path to model files (default: `ProsusAI/finbert`)
- `finbert_batch_size`: inference batch size (default: 16)
- `finbert_max_length`: max token length (default: 512)

**Safety net:** A Celery Beat task at `:15` runs sentiment processing as a catch-up for any articles missed by the chained flow.

## Article-to-Stock Linking

Articles are linked to stocks via the `article_stocks` join table using a tiered confidence system:

| Method | Confidence | Example |
|--------|-----------|---------|
| `$TICKER` in text | 0.95 | "$XOM rallies on earnings" |
| `(TICKER)` parenthetical | 0.90 | "Exxon Mobil (XOM) reports..." |
| ALL-CAPS word matching | 0.70 | "...shares of XOM rose..." |
| Company name matching | 0.60 | "Exxon Mobil announced..." |
| Industry keyword matching | 0.45 | "OPEC cuts oil production" → all Oil & Gas Integrated stocks |

**Industry keyword matching** enables linking of broad sector/macro news to relevant stocks without explicit ticker mentions. A mapping of 80+ keywords (including cross-cutting macro themes like tariffs, sanctions, interest rates) maps to 20 sub-industries. When an article matches industry keywords but not specific tickers, it creates low-confidence links to all stocks in the matched industries.

Example: *"US could lift sanctions on more Russian oil"* → matches "sanctions" + "oil" → links to XOM, CVX, COP, OXY at confidence 0.45.

## Signal Generation + Alert Dispatch

At `:30` every hour, `generate_all_signals` iterates all active stocks and computes a composite score from four predictive components (sentiment momentum/volume, price momentum, volume anomaly), plus gated earnings surprise and options flow. RSI and trend classify market regime and apply a ±15% multiplier. **Deduplication:** before creating a new signal, the generator queries the most recent signal for each stock and skips creation if the direction, strength, and composite score (within a `SIGNAL_DEDUP_THRESHOLD` of 0.005) are unchanged — preventing near-identical signals from accumulating when underlying data barely moves between hourly runs.

| Component (default weight) | Source | Calculation |
|---------------------|--------|-------------|
| Sentiment momentum (40%) | `sentiment_scores` (48h) | Exponentially weighted avg (half-life 6h) of (positive - negative) |
| Sentiment volume (25%) | `sentiment_scores` (24h vs 20d) | Article count ratio, tanh-scaled, signed by net sentiment |
| Price momentum (20%) | `market_data_daily` (5d) | % change in close price, tanh-scaled (×5 multiplier) |
| Volume anomaly (15%) | `market_data_daily` (20d) | Trading vol vs 20-day avg, tanh-scaled, signed by price direction |
| Earnings surprise (10%, gated) | `earnings_estimates` | `tanh(surprise_pct / 5.0)` within 48h of report |
| Options flow (8%, gated) | `options_activity` | P/C + IV skew z-scores vs 20-day baseline |
| RSI / trend (regime only) | `market_data_daily` | Multiplier: extreme RSI dampens 15%; confirming trend boosts 15% |

Weights are loaded from `signal_weights` table (per-sector or global fallback), falling back to defaults if no adaptive weights exist yet.

**Thresholds:** |composite| > 0.6 = strong, > 0.35 = moderate, else weak. Direction: > 0.01 = bullish, < -0.01 = bearish.

**Alert flow:** For moderate+ signals, `dispatch_alerts` is chained via `.delay()`. It matches against active `AlertConfig` records (by stock, strength, direction), then sends notifications:
- **Discord**: Embedded message via webhook URL (per-user or global)
- **Email**: HTML email via SMTP (smtplib, run in thread to avoid blocking)

Each attempt is logged in `AlertLog` with success/error status.

## Signal Feedback Loop

### Outcome Evaluation (`:45` hourly)

After signals are generated, `evaluate_signal_outcomes` checks signals that have reached their evaluation window (1, 3, or 5 trading days). For each:
1. Fetches the closing price at signal generation and at the evaluation date
2. Computes price change percentage
3. Determines correctness: bullish + price up = correct, bearish + price down = correct
4. Stores result in `signal_outcomes` table

### Adaptive Weight Optimization (4 AM daily)

`compute_adaptive_weights` analyzes evaluated outcomes per sector to find optimal component weights:
1. For each sector with sufficient samples (configurable minimum), checks which components' sign aligned with actual price direction
2. Components that predicted direction more accurately get higher weights
3. Weights are clamped to configurable min/max bounds and normalized to sum to 1.0
4. Results stored in `signal_weights` table (upserted per sector + global fallback)

## ML Signal Ensemble

LightGBM binary classifiers trained per-sector (+ global fallback) to predict signal correctness. Disabled by default (`ML_ENSEMBLE_ENABLED=true` to activate).

**Training (4:30 AM daily):**
1. Query `SignalOutcome` + `Signal` for 6 component scores + `is_correct` label
2. Per-sector: chronological train/val split (80/20), minimum 100 samples
3. Train LightGBM with conservative params (`num_leaves=15`, `num_threads=1`) for ARM compatibility
4. Store model file to disk, upsert `ml_models` row with validation metrics + feature importances
5. Train global fallback model from all sectors combined

**Inference (inline in signal generation):**
1. Load active model for stock's sector (or global fallback) from module-level cache
2. Predict P(correct) from 6 component scores (< 0.1ms)
3. High confidence correct → agree with rule-based direction; high confidence wrong → disagree; near 0.5 → neutral
4. Store `ml_score` (signed [-1,1]), `ml_direction`, `ml_confidence` on the Signal

**Resource footprint:** ~50MB peak during training, ~20-50KB model files, < 0.1ms inference. Negligible on 2 ARM core / 12GB VM.

## Backtesting Engine

The backtesting engine replays signal generation over historical OHLCV data to validate trading strategies. It runs as a Celery task on the `signals` queue.

### Two Modes

| Mode | Components | Data Range |
|------|-----------|------------|
| **Technical** | Live formula with sentiment omitted (price + volume predictive; RSI/trend as regime multiplier) | Full historical (~30+ years) |
| **Full** | Same formula plus historical sentiment momentum + volume. Earnings/options are not replayed. | Limited to period since sentiment scraping began |

Both modes import `combine_component_scores` from `worker/utils/signal_formula.py` — the same combiner used by live signal generation.

### Technical Mode

Sentiment inputs are `None` (treated as 0.0). Default weights are 40/25/20/15 with earnings and options gated off. Strong signals are rarer than the old RSI/trend-additive formula; that is intentional so backtests compare against live scoring.

### Engine Flow

```
1. Warmup period: 60 days (for SMA50 calculation)
2. For each trading day after warmup:
   a. Compute OHLCV signal components from historical slices
   b. If "full" mode: compute sentiment components from pre-fetched data
   c. Weighted sum → composite score → classify direction + strength
   d. Check stop-loss / take-profit (if configured, before signal logic):
      - If price dropped ≥ stop_loss_pct from entry → SELL (exit_reason="stop_loss")
      - If price rose ≥ take_profit_pct from entry → SELL (exit_reason="take_profit")
   e. Trading logic:
      - No position + bullish + meets min strength → BUY (invest position_size_pct of cash)
        - Apply slippage on entry price, deduct commission from allocation
      - In position + bearish + meets min strength → SELL (exit_reason="signal")
        - Apply slippage on exit price, deduct commission from proceeds
   f. Record equity point (cash + position market value)
3. Force-close any open position at end (exit_reason="end_of_period")
4. Compute performance metrics from equity curve + trade log
5. Fetch benchmark (SPY or configured ticker) OHLCV, compute alpha/beta
```

### Transaction Costs

| Parameter | Default (API) | Range | Effect |
|-----------|--------------|-------|--------|
| `commission_pct` | 0.1% | 0–5% | Deducted on both buy (from allocation) and sell (from proceeds) |
| `slippage_pct` | 0.05% | 0–5% | Price adjusted unfavorably: buy at `close × (1 + slippage)`, sell at `close × (1 - slippage)` |
| `position_size_pct` | 100% | 10–100% | Fraction of cash allocated per trade; remaining cash stays uninvested |
| `stop_loss_pct` | null | 0–50% | Auto-exit if position drops by this % from entry price |
| `take_profit_pct` | null | 0–500% | Auto-exit if position rises by this % from entry price |

### Performance Metrics

| Metric | Calculation |
|--------|-------------|
| Total return | `(final_equity - starting_capital) / starting_capital × 100` |
| Annualized return | `((final/start)^(252/trading_days) - 1) × 100` |
| Sharpe ratio | `mean(daily_returns) / std(daily_returns) × sqrt(252)` |
| Max drawdown | Largest peak-to-trough decline in equity curve |
| Win rate | % of completed round-trip trades with positive return |
| Alpha | Strategy annualized return − benchmark annualized return |
| Beta | `Cov(strategy_daily, benchmark_daily) / Var(benchmark_daily)` |

### Benchmark Comparison

After the main backtest completes, the task fetches OHLCV for the benchmark ticker (default SPY) and computes:
- Benchmark equity curve normalized to starting capital
- Total and annualized benchmark returns
- Alpha (excess annualized return over benchmark)
- Beta (systematic risk measure from daily return covariance)

### Sector Backtests

When targeting a sector, capital is divided equally across tickers. Each ticker runs independently, then results are aggregated: equity curves summed per date, trade logs merged, metrics computed on the combined curve.

### Storage

- Equity curve stored as JSON text in the `backtests` table (~100KB for 10 years). Written once, consumed whole for charting.
- Benchmark equity curve stored as JSON text alongside strategy curve.
- Individual trades stored in `backtest_trades` with CASCADE delete on the parent backtest.
- Each sell trade records `exit_reason`: `signal`, `stop_loss`, `take_profit`, or `end_of_period`.

### CSV Export

`GET /backtests/{id}/export?type=trades` or `?type=equity_curve` returns a streaming CSV download.

## Network Security

- Postgres (5432) and Redis (6379): internal VPC only, not exposed to internet
- Nginx (80/443): only public-facing service
- Compute VM connects to Docker VM over Oracle VCN internal subnet
- Oracle Cloud security lists restrict inter-VM traffic to required ports only
- HTTPS via Let's Encrypt on nginx

## Resource Budget (Free Tier)

| Resource | Docker VM | Compute VM |
|----------|-----------|------------|
| CPU | 2 ARM cores | 2 ARM cores |
| RAM | 12 GB | 12 GB |
| Storage | 100 GB | 100 GB |
| Network | Internal VCN | Internal VCN |

### Memory allocation (Compute VM)
- OS + overhead: ~1 GB
- FinBERT model: ~1.5 GB
- Celery workers (2): ~2 GB
- Python runtime: ~0.5 GB
- Buffer: ~7 GB free

## Testing

### Test Pyramid

| Layer | Framework | Count | Location |
|-------|-----------|-------|----------|
| Unit tests | pytest | 555+ | `backend/tests/` (excluding `integration/`) |
| Mutation tests | mutmut | 3 tiers | `backend/tests/test_mutation/` |
| Integration tests | pytest + httpx | 34 | `backend/tests/integration/` |
| E2E tests | Playwright | 10 | `frontend/e2e/` |
| Frontend unit | Vitest + Testing Library | — | `frontend/src/**/*.test.ts` |

### Unit Tests

Cover ticker extraction, text cleaning, scraper parsers, sentiment analysis, signal scoring, signal intelligence, event classification, duplicate detection, technical indicators, feedback loop, backtester (costs, sizing, stop-loss, benchmark), market data, maintenance, password validation, and secret key security.

### Mutation Tests (3 Tiers)

Mutation testing verifies that tests detect real code changes. Run via `mutmut` on critical calculation modules:

- **Tier 1**: `technical_indicators.py` — RSI, SMA, MACD, Bollinger Bands
- **Tier 2**: `backtester/metrics.py`, `backtester/engine.py`, `component_scores.py` — Sharpe ratio, drawdown, scoring functions
- **Tier 3**: `duplicate_detector.py`, `ticker_extractor.py`, `signal_generator.py` — threshold boundaries, dedup logic

### Integration Tests

Full HTTP → FastAPI → SQLAlchemy → PostgreSQL cycle using `httpx.AsyncClient` with `ASGITransport`. Uses `NullPool` for test isolation across event loops.

**Suites:** auth flow (register/login/refresh/profile/password), stocks & watchlist CRUD, signals & admin endpoints, error handling (auth failures, pagination bounds, API keys).

Requires a running Postgres instance (`TEST_DATABASE_URL` env var). Tables are truncated between tests for isolation.

### E2E Tests (Playwright)

Browser-based tests with custom fixtures for authenticated and admin page contexts:

- Auth: login form, invalid credentials, unauthenticated redirect, successful login
- Navigation: sidebar links, page transitions
- Signals: page load, tab structure
- Admin: admin access, non-admin redirect

### CI Pipeline

GitHub Actions runs on every push/PR:
1. **Lint** — ruff check + format
2. **Unit tests** — pytest with coverage reporting (`fail_under=60%`)
3. **Integration tests** — pytest with Postgres service container
4. **Docker build** — validates container builds

Weekly mutation testing runs on Sunday at 3 AM UTC (`.github/workflows/mutation.yml`).
