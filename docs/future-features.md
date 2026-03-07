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

### Enhanced News Intelligence

**Motivation:** Improve signal quality with better article understanding.

**Approach:**
- **Event classification**: Categorize articles (earnings, M&A, regulatory, product launch, etc.) beyond FinBERT positive/negative
- **Named entity extraction**: Pull out executives, companies, products mentioned
- **Duplicate/near-duplicate detection**: Cluster articles about the same event to avoid over-counting sentiment
- **Source credibility weighting**: Weight sentiment by source reliability (SEC filings > Reddit)

**Key decisions:**
- Whether to use a larger LLM (Claude/GPT) for event classification or fine-tune a smaller model
- Real-time vs batch processing for entity extraction
- How to build source credibility scores (manual vs learned)

### Real-time Data Streaming

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

### Social Sentiment Integration

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

### Options Flow / Unusual Activity

**Motivation:** Options activity is a leading indicator for stock moves.

**Approach:**
- Scrape unusual options activity from public sources (Finviz, Barchart)
- Track put/call ratios, unusual volume, large block trades
- Add as a signal component or separate indicator on stock detail page

**Key decisions:**
- Data source reliability and update frequency
- Whether to integrate into composite score or display separately
- Historical options data availability

### Machine Learning Signal Ensemble

**Motivation:** Replace hand-tuned composite scoring with learned models.

**Approach:**
- Train gradient boosted model (XGBoost/LightGBM) on historical features → price direction
- Features: all current signal components + technical indicators + sentiment features
- Per-sector or per-stock models depending on data availability
- A/B test ML model vs current rule-based scoring

**Key decisions:**
- Training data requirements (need sufficient outcome-evaluated signals)
- Model retraining frequency (daily, weekly, on-demand)
- How to handle model drift and feature importance monitoring
- Whether to replace or supplement the current adaptive weight system

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
