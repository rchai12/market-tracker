# Future Features

Context document for planned features and improvements. Each section captures the motivation, rough approach, and key decisions to make before implementation.

## Completed Phases

| Phase | Focus | Key Deliverables |
|-------|-------|-----------------|
| 1-7 | Core platform | FastAPI backend, React frontend, scraping pipeline, FinBERT sentiment, signal generation, alerts, charts, watchlists |
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

---

## Phase 12 Candidates

### Backtesting Engine

**Motivation:** Validate signal strategies against historical data before deploying them live. Currently we can only measure accuracy forward-looking via the feedback loop.

**Approach:**
- Replay historical OHLCV + sentiment data to simulate signal generation at past timestamps
- Compare simulated signals against actual price movements
- Generate performance reports: Sharpe ratio, max drawdown, win rate by sector/timeframe
- Frontend: backtest configuration page, equity curve chart, performance breakdown table

**Key decisions:**
- How far back to backtest (limited by sentiment data availability — scraping only started recently)
- Whether to store backtest results in DB or compute on-the-fly
- Simulated vs actual slippage/fees modeling

### Portfolio Simulation / Paper Trading

**Motivation:** Let users test strategies with virtual portfolios without risking real money.

**Approach:**
- Virtual portfolio model: starting capital, positions, trade history
- Auto-trade based on signal thresholds (e.g., buy on strong bullish, sell on strong bearish)
- Track P&L, position sizing, portfolio value over time
- Frontend: portfolio dashboard, trade log, performance chart

**Key decisions:**
- Position sizing strategy (fixed amount vs percentage of portfolio)
- Whether to support manual trades alongside auto-trades
- How to handle dividends, splits, after-hours gaps

### ~~Enhanced News Intelligence~~ (Done — Phase 16)

Implemented: rule-based event classification (10 categories, ~100 keywords), fuzzy duplicate detection via rapidfuzz token_set_ratio, source credibility weighting in signal scoring. Named entity extraction deferred.

### ~~Real-time Data Streaming~~ (Unfeasible)

> **Not viable on current Oracle Cloud free-tier infrastructure.** Persistent WebSocket connections for 86 tickers would create constant network load (vs current bursty hourly batch), competing with the Compute VM's 2 ARM cores already running Celery + FinBERT. Free-tier bandwidth throttling and egress limits make real-time streaming impractical. A middle ground (reducing batch interval to 15-30 min) would work within existing constraints without architectural changes.

**Motivation:** Move from hourly batch processing to real-time for faster signal generation.

**Approach:**
- WebSocket connections for live price updates (replace hourly yfinance polling)
- Server-sent events (SSE) or WebSocket push for live signal/alert delivery to frontend
- Streaming sentiment processing (process articles immediately on scrape rather than batched)

**Key decisions:**
- WebSocket provider (Polygon.io, Alpaca, IEX Cloud — all have free tiers)
- Whether frontend uses WebSocket directly or SSE for simpler server push
- How to handle market hours vs after-hours differently

### Multi-timeframe Analysis

**Motivation:** Current signals use a single timeframe. Different timeframes can provide confluence signals.

**Approach:**
- Compute indicators across multiple timeframes (daily, weekly, monthly)
- Add timeframe confluence scoring: signals that agree across timeframes are stronger
- Frontend: multi-timeframe indicator view, confluence indicator on signal cards

**Key decisions:**
- Which timeframes to support (intraday requires real-time data)
- How to weight timeframe confluence in composite score
- Whether this replaces or augments the current single-timeframe approach

### ~~Social Sentiment Integration~~ (Deferred)

> **Deprioritized due to signal noise.** Social platforms (StockTwits, Twitter/X) are heavily polluted by bots, spam, and pump-and-dump campaigns. Twitter/X API is $100/month minimum for read access. StockTwits is free but noisy — user-tagged sentiment is unreliable compared to FinBERT on curated news. Adding low-quality social data risks degrading signal accuracy rather than improving it. Reddit (already scraped, filtered by score >= 10) provides the best signal-to-noise ratio for retail sentiment.

**Motivation:** Reddit scraping is limited. Twitter/X, StockTwits, and other social platforms carry significant retail sentiment.

**Approach:**
- Add scrapers for StockTwits (public API), Twitter/X (if API access available)
- Social-specific sentiment analysis (FinBERT may not capture internet slang well)
- Volume-weighted social sentiment as a new signal component

**Key decisions:**
- API access and rate limits (Twitter API pricing, StockTwits terms)
- Whether to add a separate "social sentiment" component vs mixing into existing sentiment
- Handling bot/spam detection in social data

### Improved Frontend UX

**Motivation:** Polish and extend the dashboard for power users.

**Approach:**
- **Customizable dashboard**: Drag-and-drop widget layout, saved layouts per user
- **Chart drawing tools**: Support lines, Fibonacci, annotations on TradingView charts
- **Comparison mode**: Overlay multiple tickers on the same chart
- **Alert notifications in-app**: Toast/bell notifications, not just Discord/email
- **Mobile responsive**: Current layout is desktop-focused
- **Keyboard shortcuts**: Power-user navigation (j/k for next/prev stock, etc.)

### ~~Options Flow / Unusual Activity~~ (Done — Phase 18)

Implemented: yfinance options chain data (nearest 3 expirations per ticker), aggregated daily snapshots with put/call ratio, volume-weighted IV, ATM strike IV identification, and IV skew computation. CBOE market-wide put/call ratio from public CSV. 7th signal component (options score) using PCR anomaly (60%) + IV skew signal (40%) vs 20-day baseline, tanh-scaled. Feature-toggled via `OPTIONS_FLOW_ENABLED` (default off). Frontend: P/C ratio + IV summary cards, call/put volume comparison, P/C ratio history bar chart, data quality badges. Admin trigger for immediate fetch.

### ~~Machine Learning Signal Ensemble~~ (Done — Phase 17)

Implemented: LightGBM binary classifier trained per-sector (+ global fallback) on 6 component scores from SignalOutcome data. Runs alongside rule-based scoring for A/B comparison — does NOT replace composite scores. Admin-triggered training with automatic daily retraining at 4:30 AM. ML score, direction, and confidence stored on every signal. Frontend shows ML badge on signal cards, A/B accuracy comparison, and ML model status table with feature importances.

---

## Infrastructure Improvements

### Performance
- Frontend code splitting (bundle > 500KB currently)
- Redis caching for expensive queries (sector summaries, trending stocks)
- Database connection pooling tuning under load
- CDN for static frontend assets

### Reliability
- Database replication (read replica for heavy queries)
- Worker autoscaling based on queue depth
- Dead letter queue for failed tasks
- Health check alerts (PagerDuty/Slack when services go down)

### Observability
- Prometheus metrics export (request latency, task duration, queue depth)
- Grafana dashboards for system monitoring
- Distributed tracing (OpenTelemetry) across API → Celery → DB
- Error tracking (Sentry integration)

### Security
- API key support (for programmatic access alongside JWT)
- OAuth2 social login (Google, GitHub)
- Two-factor authentication
- Audit logging for admin actions
