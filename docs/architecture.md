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
│  │  - scraping            │  │  - */5  health check   │   │
│  │  - sentiment           │  │  - :00  scrape all     │   │
│  │  - signals             │  │  - :05  market data    │   │
│  │  - maintenance         │  │  - :10  options chain  │   │
│  │  - default             │  │  - :12  CBOE P/C ratio │   │
│  │                        │  │  - :15  sentiment      │   │
│  │                        │  │  - */2h :20 LLM extract│   │
│  │                        │  │  - :30  gen signals    │   │
│  │                        │  │  - :35  paper portfolio│   │
│  │                        │  │         + matview      │   │
│  │                        │  │  - :45  eval outcomes  │   │
│  │                        │  │  - 18:00 insider Form 4│   │
│  │                        │  │  - 21:30 portfolio snap│   │
│  │                        │  │  - 3AM  maintenance    │   │
│  │                        │  │  - 4AM  adapt weights  │   │
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
                    │ Google News │
                    │ SEC EDGAR   │
                    │ MarketWatch │
                    │ Reddit      │
                    │ FRED        │
                    │ yfinance    │ ← also options, insider Form 4
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Scrapers   │  (Celery tasks on Compute VM)
                    │  (hourly)   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Ticker    │  $TICKER (0.95), (TICKER) (0.90),
                    │ Extraction  │  ALL-CAPS (0.70), company name (0.60)
                    │             │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Event     │  10 categories (earnings, M&A, etc.)
                    │ Classifier  │  + fuzzy dedup (rapidfuzz)
                    │ + Dedup     │  + source credibility weighting
                    │ + Quality   │  article quality score 0–1
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───┐ ┌──────▼──────┐
       │  Articles   │ │Stocks│ │ Market Data │  (Postgres on Docker VM)
       │  (raw text) │ │      │ │  (OHLCV)   │
       └──────┬──────┘ └──────┘ └──────┬──────┘
              │                        │
       ┌──────▼──────┐           ┌─────▼──────┐
       │  FinBERT    │           │  Options   │  yfinance P/C ratio
       │ Sentiment   │           │  + Insider │  Form 4 transactions
       └──────┬──────┘           └─────┬──────┘
              │                        │
       ┌──────▼──────┐                 │
       │  Sentiment  │                 │
       │   Scores    │                 │
       └──────┬──────┘                 │
              │                        │
       ┌──────▼──────┐                 │
       │ Claude Haiku│  earnings +     │
       │ LLM extract │  analyst arts   │
       └──────┬──────┘                 │
              │                        │
              └───────────┬────────────┘
                          │
                   ┌──────▼──────┐
                   │   Signal    │  rule-based composite
                   │  Generator  │  + ML inference (LightGBM)
                   │             │  → upsert daily_signal_views
                   └──────┬──────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
       ┌──────▼──────┐ ┌──▼──────┐ ┌─▼────────────┐
       │  Signals    │ │ Alerts  │ │  Daily View  │
       │  (stored)   │ │Discord  │ │  (net score, │
       │             │ │+ Email  │ │  conviction, │
       │             │ └─────────┘ │  direction)  │
       └──────┬──────┘             └──────┬───────┘
              │                           │
              └──────────┬────────────────┘
                         │
                  ┌──────▼──────┐
                  │  Outcome    │  per-signal (1/3/5d) +
                  │  Evaluator  │  daily-view (excess return
                  │             │  vs sector ETF)
                  └──────┬──────┘
                         │
              ┌──────────┼──────────┐
              │                     │
       ┌──────▼──────┐       ┌──────▼──────┐
       │  Adaptive   │       │  ML Trainer │
       │  Weights    │       │  LightGBM   │
       │ (per-sector │       │ (per-sector │
       │  + regime)  │       │  + global)  │
       └──────┬──────┘       └──────┬──────┘
              │                     │
              └──────────┬──────────┘
                         │ feeds back to Signal Generator
                  ┌──────▼──────┐
                  │  React App  │
                  │ (Dashboard, │
                  │  Portfolio, │
                  │  Charts,    │
                  │  Signals,   │
                  │  Backtest,  │
                  │  Admin)     │
                  └─────────────┘
```

## Database Schema

32 tables total.

### Entity Relationships

```
users ──< watchlist_items >── stocks
users ──< alert_configs
users ──< backtests
users ──< api_keys
stocks ──< article_stocks >── articles
stocks ──< market_data_daily
stocks ──< market_data_intraday
stocks ──< signals
stocks ──< daily_signal_views ──< daily_signal_view_outcomes
stocks ──< options_activity
stocks ──< insider_transactions
stocks ──< earnings_estimates
articles ──< sentiment_scores
signals ──< signal_outcomes
sectors ──< signal_weights
sectors ──< regime_adaptive_weights
sectors ──< ml_models
backtests ──< backtest_trades
backtests >── stocks (nullable)
backtests >── sectors (nullable)
paper_portfolios ──< paper_positions >── stocks
paper_portfolios ──< paper_trades
paper_portfolios ──< paper_portfolio_snapshots
```

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| users | Authentication and preferences | email, username, password_hash, discord_webhook_url |
| sectors | Stock groupings (Energy, Financials, Technology, ...) | name, is_active |
| stocks | ~91 tickers across 6 sectors + ETFs | ticker, company_name, sector_id, industry, is_active |
| market_data_daily | Historical OHLCV (30+ years) | stock_id, date, open/high/low/close/volume |
| market_data_intraday | Intraday prices | stock_id, timestamp, OHLCV |
| articles | Scraped news/filings | source, source_url, title, raw_text, is_processed, event_category, quality_score, duplicate_group_id, canonical_article_id, llm_extracted, metadata_ (JSONB) |
| article_stocks | Article-to-ticker mapping | article_id, stock_id, confidence |
| sentiment_scores | FinBERT analysis results | article_id, stock_id, label, positive/negative/neutral scores |
| signals | Composite trading signals | stock_id, direction, strength, composite_score, sentiment_score, sentiment_volume_score, price_score, volume_score, rsi_score, trend_score, options_score, earnings_score, analyst_score, ml_score, ml_direction, ml_confidence, has_ml, insider_score, market_regime, trading_date, reasoning |
| signal_outcomes | Per-signal accuracy (1/3/5d) | signal_id, window_days, is_correct, price_change_pct |
| daily_signal_views | Daily net view per stock/session | stock_id, trading_date, net_score, direction, conviction, signal_count, raw_signal_count, baseline_close |
| daily_signal_view_outcomes | Daily view accuracy evaluation | daily_view_id, window_days, is_correct, price_change_pct, sector_return_pct, excess_return_pct |
| signal_weights | Per-sector adaptive weights | sector_id (nullable=global), sentiment_momentum, sentiment_volume, price_momentum, volume_anomaly, earnings, options, analyst, insider, rsi, trend, accuracy_pct, sample_count |
| regime_adaptive_weights | Per-(sector, regime) adaptive weights | sector_id, regime, sentiment_momentum, sentiment_volume, price_momentum, volume_anomaly, earnings, options, analyst, insider, rsi, trend, accuracy_pct, sample_count |
| ml_models | ML model registry (one active per sector) | sector_id, model_version, training_samples, validation_accuracy, validation_f1, model_path, feature_importances |
| alert_configs | User alert preferences | user_id, stock_id, min_strength, channel |
| alert_logs | Sent alert history | signal_id, user_id, channel, success |
| watchlist_items | User watchlists | user_id, stock_id |
| scrape_logs | Scraper execution logs | source, articles_found, articles_new, errors |
| backtests | Backtest configurations + results | user_id, stock_id/sector_id, mode, status, metrics, equity_curve (JSON), commission/slippage/position_size/stop_loss/take_profit, benchmark_ticker, alpha, beta, benchmark_equity_curve (JSON) |
| backtest_trades | Individual backtest trades | backtest_id, ticker, action, price, shares, signal_score, return_pct, exit_reason |
| options_activity | Daily per-ticker options aggregates | stock_id, date, put_call_ratio, iv_skew, weighted_avg_iv, volume/OI aggregates, data_quality |
| cboe_put_call_ratio | Market-wide CBOE put/call ratio | date, put_call_ratio, equity_pc_ratio |
| earnings_estimates | EPS consensus vs actual | stock_id, earnings_date, eps_estimate, eps_actual, surprise_pct, guidance_change |
| insider_transactions | Form 4 insider trades | stock_id, insider_name, insider_title, transaction_type (P/S/A/D), shares, price_per_share, transaction_value, transaction_date |
| paper_portfolios | Simulated long-only portfolio | starting_capital, current_cash, inception_date, benchmark_ticker |
| paper_positions | Open simulated positions | portfolio_id, stock_id, entry_price, shares, stop_loss_price, take_profit_price |
| paper_trades | Closed simulated trades | portfolio_id, stock_id, entry_price, exit_price, realized_pnl, return_pct, exit_reason |
| paper_portfolio_snapshots | Daily equity vs SPY | portfolio_id, snapshot_date, total_value, equity_value, cash, benchmark_price, cumulative_return_pct, benchmark_cumulative_return_pct |
| task_failures | Dead letter queue for failed Celery tasks | task_name, task_args, exception_type, exception_message, traceback, failed_at, retried_at |
| api_keys | Per-user API key auth (SHA-256 hashed) | user_id, key_hash, key_prefix, name, is_active, last_used_at, expires_at |
| audit_logs | Admin action audit trail | user_id, action, resource, detail (JSON), ip_address, created_at |

## Signal Scoring Algorithm

Live scoring and backtests share `worker/utils/signal_formula.py` so they cannot drift. The module owns all weights, regime logic, gating, and classification.

### Components

Four base predictive components always contribute. Five additional components are gated — they only activate when data is available or features are enabled. RSI and trend are **never additive**; they classify market regime and apply a ±15% multiplier to the composite.

```
raw = w_sm * sentiment_momentum
    + w_sv * sentiment_volume
    + w_pm * price_momentum
    + w_va * volume_anomaly
    + 0.10 * earnings_score   (gated: within 48h of earnings report)
    + 0.08 * options_score    (gated: OPTIONS_FLOW_ENABLED)
    + 0.07 * analyst_score    (gated: 30-day LLM-extracted analyst articles)
    + 0.08 * ml_score         (gated: model accuracy ≥ 55% AND samples ≥ 50)
    + 0.08 * insider_score    (gated: INSIDER_FLOW_ENABLED, 30-day Form 4)

composite, market_regime = apply_regime_multiplier(raw, rsi_score, trend_score)
```

When gated components activate, the four base weights scale down proportionally so the full set always sums to 1.0. For example, with no gated components active the base weights are 40/25/20/15. With analyst + insider both active (15% combined gated), the base weights become roughly 34/21/17/13.

| Component | Default weight | Activation | Calculation |
|-----------|---------------|------------|-------------|
| sentiment_momentum | 0.40 (base) | Always | Exp-weighted avg of (positive − negative) sentiment scores, half-life 6h, 48h window |
| sentiment_volume | 0.25 (base) | Always | Article count vs 20-day baseline, tanh-scaled, signed by net sentiment direction |
| price_momentum | 0.20 (base) | Always | 5-day price change, tanh-scaled (×5 multiplier) |
| volume_anomaly | 0.15 (base) | Always | Trading volume vs 20-day avg, tanh-scaled, signed by price direction |
| earnings_score | 0.10 (gated) | EPS report within 48h | `tanh(surprise_pct / 5.0)` + guidance_change modifier (±0.20) + management_tone modifier (±0.10) from LLM extraction |
| options_score | 0.08 (gated) | OPTIONS_FLOW_ENABLED | `0.6 * -tanh(pcr_z) + 0.4 * -tanh(skew_z)` vs 20-day baseline |
| analyst_score | 0.07 (gated) | 30-day LLM-extracted analyst articles exist | `0.6 * tanh(net_rating/2) + 0.4 * tanh(mean_upside*5)` |
| ml_score | 0.08 (gated) | Model accuracy ≥ 55% AND samples ≥ 50 | LightGBM P(correct) mapped to signed [-1, 1] |
| insider_score | 0.08 (gated) | INSIDER_FLOW_ENABLED | `tanh(net_value / 500_000)`, role-weighted, sells counted at 40% |
| rsi_score | regime only | Always computed | `tanh((50 − rsi) / 50 * 2.5)` — oversold → positive, overbought → negative |
| trend_score | regime only | Always computed | `0.6 * sma_crossover + 0.4 * macd_histogram_signal` |

### Regime Multiplier

Priority order (first match wins):

1. `|rsi_score| > 0.4` → dampen composite 15%, label = `overbought` or `oversold`
2. `|trend_score| > 0.3` and trend confirms signal direction → boost 15%, label = `trending_up` or `trending_down`
3. `|trend_score| > 0.3` and trend opposes signal → dampen 15%
4. Default → no change, label = `sideways`

The `market_regime` label is stored on every signal and used by the weight optimizer to build per-(sector, regime) adaptive weights.

### Classification Thresholds

| Label | Condition |
|-------|-----------|
| Strong | `|composite| > 0.6` |
| Moderate | `|composite| > 0.35` |
| Weak | Everything else |
| Bullish | `composite > 0.01` |
| Bearish | `composite < -0.01` |
| Neutral | `|composite| <= 0.01` |

## Daily Signal Views (Phase 24 / 24b)

Each :30 signal generation upserts a `daily_signal_views` row — one net view per stock per trading session. This collapses multiple intra-day signals into a single learning unit and is the primary input to the adaptive weight optimizer and ML trainer.

### Trading Date Assignment

The `trading_date` on each signal is the next market-session close the signal predicts:

- Weekday before 16:00 ET (including pre-market) → same-day close
- After 16:00 ET or weekend → next calendar day (then resolved to the next actual trading session from `market_data_daily` to skip holidays)

### 4-Hour Bucket Collapsing (Phase 24b)

Before netting, signals are collapsed into three 4-hour ET buckets. Only the strongest signal (`|composite_score|`) per bucket contributes to the net view. This prevents a single noisy hour from dominating a session.

| Bucket | ET Window |
|--------|-----------|
| pre_market | Before 09:30 |
| morning | 09:30 – 13:30 |
| afternoon | 13:30 – 16:00 |

After bucketing, `raw_signal_count` records how many signals existed before collapsing; `signal_count` records the number of buckets that contributed.

### Net Score Calculation

The net score is a magnitude- and recency-weighted average over bucketed signals:

```
weight(signal) = |composite_score| * exp(-λ * hours_before_close)
                 where λ = 0.15

net_score = Σ weight(s) * sign(direction(s)) / Σ weight(s)
conviction = |net_score|
```

The recency weight (`λ=0.15`, half-life ≈ 4.6 hours) means signals generated closer to the market close are trusted more than pre-market signals when they conflict.

### Learning Filter

Daily views with `conviction < 0.20` are stored but excluded from the learning loop (weight optimizer and ML trainer). This avoids training on ambiguous sessions where intra-day signals cancelled out.

### Outcome Evaluation

Daily-view outcomes are evaluated against **excess return**: stock return minus the sector ETF return (XLE for Energy, XLF for Financials, XLK for Technology, XLC for Communication Services, XLY for Consumer Discretionary). Market ETFs use absolute return since there is no sector benchmark for them.

`is_correct` = direction was `bullish` and excess return > 0, or `bearish` and excess return < 0.

Both `sector_return_pct` and `excess_return_pct` are stored alongside `price_change_pct` for analysis.

## Adaptive Learning Loop

The system learns from outcomes to improve signal accuracy over time. All learning reads from `daily_signal_view_outcomes`, not individual `signal_outcomes`.

### Weight Optimizer (4:00 AM daily)

`compute_adaptive_weights` loads 1-day daily-view outcomes with `conviction ≥ 0.20`. For each outcome, the contributing signals (grouped by `stock_id, trading_date`) cast weighted votes: each signal's vote weight is `abs(composite_score) * recency_weight`, scaled to a proportional share of the session's total weight. The vote magnitude is the return scaled by that share.

The optimizer then builds per-(sector, regime) weight vectors using `return_weighted` votes and writes them to two tables:

- `signal_weights` — per-sector weights (sector_id nullable = global fallback)
- `regime_adaptive_weights` — per-(sector, regime) pairs when enough samples exist

**Weight lookup priority at signal generation time:**

```
(sector_id, market_regime) → regime_adaptive_weights
(None, market_regime)      → regime_adaptive_weights (global regime)
sector_id                  → signal_weights
None                       → signal_weights (global)
code defaults              → 40/25/20/15 + gated defaults
```

The `majority_regime` among a session's bucketed signals determines which regime key to use at learning time. RSI and trend weights are always written as 0.0 (regime context only, never additive).

### ML Trainer (4:30 AM daily)

`train_ml_models` trains per-sector LightGBM binary classifiers. Features are the weighted-mean 6-vector per daily view (magnitude-weighted over contributing signals):

```
features = [sentiment_score, sentiment_volume_score, price_score,
            volume_score, rsi_score, trend_score]
label    = daily_view_outcome.is_correct (1-day window)
```

The per-view feature vector is computed by `aggregate_feature_vector()` in `daily_aggregation.py`. Training uses a chronological 80/20 train/val split. Minimum 50 samples required. A global fallback model is trained from all sectors combined.

### ML Promotion (Phase 23a)

After training, the model's `validation_accuracy` and `training_samples` are checked against configurable thresholds (default: accuracy ≥ 55%, samples ≥ 50). When both thresholds are met, the model is considered **qualified** and the `has_ml=True` flag is written onto subsequent signals. When qualified, `ml_score` enters the composite as an 8% component. When unqualified, `ml_score` is still stored for A/B comparison but `has_ml=False` and it does not affect the composite.

The backtester always sets `has_ml=False` — it never replays ML inference.

### Reset Learning Layer

`POST /api/admin/reset-learning-layer` (admin only) truncates all four learning tables:
`signal_outcomes`, `daily_signal_view_outcomes`, `ml_models`, `signal_weights`, `regime_adaptive_weights`. This is the safe starting point when the signal formula changes significantly and historical learning data is no longer meaningful.

## Single-Source-of-Truth (SSOT) Modules

After multiple refactoring passes, critical calculations live in exactly one place:

| Module | What it owns | Who imports it |
|--------|-------------|----------------|
| `worker/utils/signal_formula.py` | Weights, regime multiplier, gating, ML qualification, classification thresholds | `signal_generator`, backtester, weight optimizer |
| `worker/utils/component_math.py` | Pure scorers: price/volume tanh kernels, RSI calculation, sentiment decay, trend formula | `component_scores` task (queries DB then calls it), backtester (passes arrays directly) |
| `worker/utils/market_data_queries.py` | `close_on_or_before`, `nth_trading_day_close`, `latest_close(s)`, `recent_closes`, `recent_close_volume` | Outcome evaluator, paper portfolio task, portfolio API, component scorers |
| `worker/utils/learning_queries.py` | 1-day daily-view outcome query, signals-for-views grouping | Weight optimizer, ML trainer |
| `worker/utils/performance_metrics.py` | Sharpe ratio, max drawdown, Jensen alpha/beta (rf=0) | Paper portfolio, backtester |
| `worker/utils/daily_aggregation.py` | Trading-date assignment, 4-hour buckets, recency weights, net-view calculation, feature aggregation, sector ETF map, proportional vote credit | Signal generator (upsert), outcome evaluator, weight optimizer, ML trainer |

This design prevents the live pipeline and the backtester from computing the same formula differently, which was a class of bugs found and fixed in the post-Phase 21 refactoring.

## Sentiment Analysis Pipeline

FinBERT (ProsusAI/finbert) runs as a singleton on the Compute VM, lazy-loaded on first use.

**Flow:**
1. Scraper orchestration completes → automatically chains `process_new_articles_sentiment`
2. Task queries all articles where `is_processed = false` with eager-loaded `article_stocks`
3. For each article, selects best text source: `raw_text` → `summary` → `title`
4. FinBERT analyzes text (chunking at ~512 tokens for long articles, averaging scores across chunks)
5. Stores `SentimentScore` per article-stock pair
6. Marks article as `is_processed = true`

A catch-up task at `:15` runs the same task to process any articles missed by the chain.

**Quality gates applied before signal inclusion:**
- `quality_score ≥ 0.40`: composite score from source credibility (40%), quantitative content (25%), ticker confidence (25%), length (10%)
- `canonical_article_id` check: non-canonical duplicates (grouped by rapidfuzz fuzzy dedup) are excluded from signal scoring

## LLM Extraction Pipeline

When `LLM_EXTRACTION_ENABLED=true`, Claude Haiku (`claude-haiku-4-5-20251001`) runs every 2 hours at `:20` via the Anthropic SDK.

**Two extraction targets (shared 50-article/run cap):**

| Target | Article category | Extracted fields | Stored in |
|--------|-----------------|------------------|-----------|
| Earnings | `earnings` event category | `guidance_change` (raised/lowered/maintained/none), `management_tone` (float) | `earnings_estimates.guidance_change`, `article.metadata_` |
| Analyst ratings | `analyst_rating` event category | `rating_change`, `price_target`, `analyst_firm` | `article.metadata_` (JSONB) |

**Gate:** `quality_score ≥ 0.60` required. Articles with empty text or no content are skipped (increments a skip counter). `articles.llm_extracted` is `NULL` until attempted, then `true` or `false`.

**How extracted data feeds signals:**
- `management_tone` modifies `earnings_score` by ±0.10
- `guidance_change` modifies `earnings_score` by ±0.20
- `rating_change` + `price_target` → `analyst_score` component (gated 7%)

## Insider Trading (Phase 23b)

yfinance `Ticker.insider_transactions` is scraped daily at 18:00 UTC when `INSIDER_FLOW_ENABLED=true`.

**Scoring (`insider_score`):**
```
net_value = Σ role_weight(title) * tx_value * sign(type)
            where purchases count +1, sales count −0.4 (sells discounted 60%)
                  CEO/CFO role_weight = 1.5x, others = 1.0x
                  30-day rolling window

insider_score = tanh(net_value / 500_000)
```

Stored in `insider_transactions` with deduplication on (stock_id, insider_name, transaction_date, transaction_type, shares). The stock-detail page shows an Insider Activity table. The signal detail panel shows the `insider_score` bar in the Gated section of ComponentBreakdown.

## Article-to-Stock Linking

Articles are linked to stocks via the `article_stocks` join table using a tiered confidence system:

| Method | Confidence | Example |
|--------|-----------|---------|
| `$TICKER` in text | 0.95 | "$XOM rallies on earnings" |
| `(TICKER)` parenthetical | 0.90 | "Exxon Mobil (XOM) reports..." |
| ALL-CAPS word matching | 0.70 | "shares of XOM rose..." |
| Company name matching | 0.60 | "Exxon Mobil announced..." |

Reddit articles are isolated from company-name and ALL-CAPS matching to reduce false positives from informal writing. Each article also receives a `quality_score` (0–1) that determines whether it is eligible for signal scoring (gate: ≥ 0.40) and LLM extraction (gate: ≥ 0.60).

**Duplicate detection:** rapidfuzz `token_set_ratio` matches article titles across sources within 24-hour windows. Duplicate groups share a `duplicate_group_id`. Only the `canonical_article_id` (oldest in group) contributes to signal scoring.

## Signal Generation

At `:30` every hour (weekdays), `generate_all_signals` iterates all active stocks and:

1. Computes 9 component scores (sentiment momentum/volume, price momentum, volume anomaly, plus gated: earnings, options, analyst, insider, ML)
2. Calls `combine_component_scores` from `signal_formula.py` to apply weights, gating, and regime multiplier
3. Runs ML inference (LightGBM) if `ML_ENSEMBLE_ENABLED=true`, stores `ml_score/ml_direction/ml_confidence`; if the model qualifies, re-runs combine with `has_ml=True`
4. Assigns a `trading_date` via `trading_date_lower_bound()` → resolves to next available session from `market_data_daily`
5. Upserts `daily_signal_views` (bucket → net score → conviction → direction)
6. Deduplicates: skips creation if the previous signal has identical direction, strength, and composite within ±0.005
7. Chains `dispatch_alerts` for moderate+ signals

**Weights used at scoring time** follow the lookup hierarchy: (sector, regime) → (global, regime) → sector → global → code defaults. The current `market_regime` label (from the regime multiplier) is used to select the regime-conditional weight row.

## Paper Portfolio (Phase 22a)

A simulated long-only portfolio runs automatically when `PAPER_PORTFOLIO_ENABLED=true`.

**Position management (:35 task, weekdays only):**
- Open: bullish signal with strength ≥ moderate → allocate 10% of mark-to-market equity; max 10 open positions, max 3 per sector
- Close triggers: stop-loss (position down 8% from entry), take-profit (position up 20% from entry), signal reversal (bearish moderate+ signal on a held ticker)
- `exit_reason` on closed trades: `stop_loss`, `take_profit`, `signal_reversal`

**Daily snapshot (21:30 UTC):**
- Records portfolio equity vs SPY benchmark
- Computes Sharpe ratio, max drawdown, Jensen alpha/beta via `performance_metrics.py`

**API endpoints:** summary, positions, trades, performance curve, stats (Sharpe/drawdown/alpha/beta/win-rate). The `/portfolio` page shows equity curve, open positions, trade history with exit-reason badges, and metrics.

## Backtesting Engine

The backtesting engine replays signal generation over historical OHLCV data. It runs as a Celery task on the `signals` queue.

### Two Modes

| Mode | Components Active | Sentiment Data |
|------|-----------------|----------------|
| Technical | Price + volume predictive; RSI/trend as regime multiplier | Omitted (treated as 0) |
| Full | All of technical + historical sentiment momentum + volume | Uses stored sentiment scores |

Earnings, options, analyst, and insider are never replayed in either mode. `has_ml` is always `False` in the backtester. Both modes import `combine_component_scores` from `signal_formula.py`.

### Engine Flow

```
1. Warmup period: 60 days (for SMA50 baseline)
2. For each trading day after warmup:
   a. Compute OHLCV signal components from historical slices
   b. If "full" mode: compute sentiment components
   c. combine_component_scores → direction + strength
   d. Check stop-loss / take-profit before signal logic
   e. Trading logic:
      - No position + bullish + meets min strength → BUY
        (invest position_size_pct of cash, apply slippage, deduct commission)
      - In position + bearish + meets min strength → SELL
        (apply slippage, deduct commission)
   f. Record equity point (cash + position market value)
3. Force-close open position at end (exit_reason="end_of_period")
4. Compute performance metrics
5. Fetch benchmark OHLCV, compute alpha/beta via performance_metrics.py
```

### Transaction Costs

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `commission_pct` | 0.1% | 0–5% | Deducted on buy (from allocation) and sell (from proceeds) |
| `slippage_pct` | 0.05% | 0–5% | Buy at `close × (1 + slippage)`, sell at `close × (1 - slippage)` |
| `position_size_pct` | 100% | 10–100% | Fraction of cash per trade |
| `stop_loss_pct` | null | 0–50% | Auto-exit if position drops by this % from entry |
| `take_profit_pct` | null | 0–500% | Auto-exit if position rises by this % from entry |

### Performance Metrics

All metrics are computed by `worker/utils/performance_metrics.py` (Sharpe, max drawdown, Jensen alpha/beta) and used by both the backtester and the paper portfolio.

| Metric | Calculation |
|--------|-------------|
| Total return | `(final_equity − starting_capital) / starting_capital × 100` |
| Annualized return | `((final/start)^(252/trading_days) − 1) × 100` |
| Sharpe ratio | `mean(daily_returns) / std(daily_returns) × sqrt(252)`, rf = 0 |
| Max drawdown | Largest peak-to-trough decline in equity curve |
| Win rate | % of completed trades with positive return |
| Jensen alpha | `(mean(Rp) − beta × mean(Rb)) × 252 × 100`, rf = 0 |
| Beta | `Cov(Rp, Rb) / Var(Rb)` on aligned daily decimal returns |

## Data Pipeline Schedule

```
Initialization:
  make seed-all → seed ~91 tickers across 6 sectors + backfill full OHLCV history

Every 5 minutes:
  */5  → health check (DB + Redis + queue depth) → Discord alert if unhealthy (15-min throttle)

Hourly (weekdays unless noted):
  :00  → fan-out 7 scrapers → store articles, extract tickers, classify events, dedup → chain FinBERT sentiment
  :05  → fetch market data via yfinance (5-day window) → invalidate market-data cache
  :10  → fetch options chain via yfinance (OPTIONS_FLOW_ENABLED)
  :12  → fetch CBOE put/call ratio (OPTIONS_FLOW_ENABLED)
  :15  → sentiment catch-up (process any unprocessed articles)
  :20  → LLM extraction every 2 hours (LLM_EXTRACTION_ENABLED; quality_score ≥ 0.60; 50 articles/run)
  :30  → generate composite signals + upsert daily_signal_views + dispatch alerts → invalidate signals cache
  :35  → update paper portfolio (close/open positions, weekday gate in-task) + refresh materialized views
  :45  → evaluate signal outcomes (1/3/5d per-signal) + daily-view outcomes (excess return vs sector ETF)

Daily:
  06:00 → fetch earnings calendars via yfinance
  18:00 → fetch insider Form 4 transactions via yfinance (INSIDER_FLOW_ENABLED)
  21:30 → snapshot paper portfolio equity vs SPY (PAPER_PORTFOLIO_ENABLED)
  03:00 → data maintenance: compress old article text, clean logs, purge weak signals, trim task failures (30d) + audit logs (90d)
  04:00 → compute adaptive weights: per-(sector, regime) return-weighted votes from 1-day daily-view outcomes
  04:30 → train ML models: per-sector LightGBM from daily-view feature vectors (ML_ENSEMBLE_ENABLED)
```

## Redis Caching Layer

Six high-traffic read endpoints are cached in Redis using the `@cached()` decorator from `app/core/cache.py`:

| Endpoint | TTL | Invalidated by |
|----------|-----|---------------|
| Sector summary | Configurable | Sentiment task, signal generator |
| Trending stocks | Configurable | Sentiment task, signal generator |
| Technical indicators | Configurable | Market data task |
| Signal weights | Configurable | Weight optimizer |
| Today's predictions | Configurable | Signal generator |
| DB stats | Configurable | Maintenance task |

Cache keys are deterministic from endpoint path + query parameters. SCAN-based invalidation clears all keys matching a pattern (e.g., all sector-summary keys when sentiment updates). The Celery tasks call the invalidation helper after writing new data.

## Infrastructure

### API Authentication

Two authentication methods are accepted on all protected endpoints via `get_current_user`:

- **JWT Bearer tokens**: issued at login, 30-minute access tokens, refresh tokens
- **API keys**: `sp_` prefix + 32 hex chars (SHA-256 hashed in DB), max 5 per user, soft-revoke, optional expiry. Used for automated access.

Admin endpoints use `get_current_admin` (requires `is_admin=True` on the user).

### Dead Letter Queue

Celery `task_failure` signal writes to the `task_failures` table for all tasks that exhaust retries. `GET /api/admin/task-failures` lists them. `POST /api/admin/task-failures/{id}/retry` re-queues via `send_task()`.

### Admin Audit Logging

All admin POST actions call `record_audit()` which writes to `audit_logs`. `GET /api/admin/audit-log` returns paginated history.

### Health Checks

`GET /api/health?detail=true` checks DB connectivity, Redis connectivity, and returns component status. A separate Celery task runs every 5 minutes to check DB/Redis/queue depth and sends a Discord webhook if any check fails (throttled to one alert per 15 minutes).

### Slow Query Detection

SQLAlchemy `before_cursor_execute` / `after_cursor_execute` event listeners measure every query. Queries exceeding the threshold (default 500ms) emit a structured log warning with the SQL and duration.

### Security

- Postgres (5432) and Redis (6379): internal VPC only
- Nginx (443): HTTPS with Let's Encrypt, HSTS, CSP, security headers
- Rate limiting on `/api/auth/`: 5 req/min per IP
- Password complexity: min 8 chars, uppercase + lowercase + digit
- `detect-secrets` pre-commit hook

## Historical Data Initialization

On first setup, `scripts/seed_historical_data.py` backfills the full available price history for all tickers via yfinance (`period="max"`), providing ~30+ years of daily OHLCV (~340K rows, ~50MB). The seed is idempotent (upserts via `ON CONFLICT DO UPDATE`) and skips tickers with 5,000+ rows.

This depth matters because the signal algorithm's 20-day baselines for price momentum and volume anomaly need at least 20 sessions of history before generating meaningful signals. Having 30+ years enables meaningful backtesting from day one.

## Technical Indicators

All indicators are computed on-the-fly from stored OHLCV data by `worker/utils/technical_indicators.py` (no extra DB tables):

| Indicator | Parameters | Purpose |
|-----------|-----------|---------|
| SMA | 20-period, 50-period | Moving average overlays, trend direction for regime multiplier |
| EMA | Configurable period | MACD calculation building block |
| RSI | 14-period (Wilder's) | Overbought/oversold detection for regime multiplier |
| MACD | Fast=12, Slow=26, Signal=9 | Trend momentum for regime multiplier and MACD sub-chart |
| Bollinger Bands | 20-period, 2 std deviations | Volatility visualization on price chart |

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
| Unit tests | pytest | 905+ | `backend/tests/` (excluding `integration/`) |
| Mutation tests | mutmut | 3 tiers, ~138 killing tests | `backend/tests/test_mutation/` |
| Integration tests | pytest + httpx | 37 | `backend/tests/integration/` |
| E2E tests | Playwright | 10 | `frontend/e2e/` |
| Frontend unit | Vitest + Testing Library | — | `frontend/src/**/*.test.ts` |

### Unit Tests

Cover ticker extraction, text cleaning, scraper parsers, sentiment analysis, signal scoring, signal intelligence, event classification, duplicate detection, technical indicators, feedback loop (including return-weighted votes, analyst/insider in optimizer, regime weight fallback), backtester (costs, sizing, stop-loss, benchmark), market data, maintenance, password validation, secret key security, paper portfolio (close/open gates, snapshot returns, Sharpe/drawdown, beat/skip guards), ML promotion (accuracy/sample gate, weight scaling, has_ml combine), insider Form 4 (role weights, sell discount, DataFrame parse), shared `component_math` (live/backtest kernel parity), shared `performance_metrics` (Jensen alpha/Sharpe/drawdown), daily aggregation (net score, trading_date, excess return vs sector ETF, 4-hour buckets, recency weights), shared close lookups, shared learning loaders.

### Mutation Tests (3 Tiers)

Mutation testing verifies that tests detect real code changes. Run via `mutmut` on critical calculation modules:

- **Tier 1**: `technical_indicators.py`, `backtester/metrics.py`, `backtester/engine.py`, `component_scores.py`
- **Tier 2**: `signal_generator.py`, `weight_optimizer.py`, `backtester/benchmark.py`, `security.py`, `dependencies.py`
- **Tier 3**: `cache.py`, `event_classifier.py`, `duplicate_detector.py`, `ticker_extractor.py`

### Integration Tests

Full HTTP → FastAPI → SQLAlchemy → PostgreSQL cycle using `httpx.AsyncClient` with `ASGITransport`. Uses `NullPool` for test isolation. Covers auth flow, stocks/watchlist CRUD, signals/admin endpoints (including daily-views, reset-learning-layer 403), and error handling.

### CI Pipeline

GitHub Actions runs on every push/PR:
1. **Lint** — ruff check + format
2. **Unit tests** — pytest with coverage (`fail_under=60%`)
3. **Integration tests** — pytest with Postgres service container
4. **Docker build** — validates container builds

Weekly mutation testing runs on Sunday at 3 AM UTC (`.github/workflows/mutation.yml`).
