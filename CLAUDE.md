# Stock Predictor

Sentiment-driven stock market prediction system. Scrapes financial news, runs FinBERT sentiment analysis, correlates with market data, generates composite trading signals, and surfaces everything through a React dashboard with Discord/email alerts.

## Current Status

**Phase 15 (signal intelligence) complete. System deployed and operational on Oracle Cloud.** All core features built through Phase 7. Phase 8 added hardening + deployment. Phase 9 added indexes, data retention, materialized views, and admin endpoints. Phase 10 added signal feedback loop (outcome tracking, adaptive weights, accuracy UI). Phase 11 added technical indicators (RSI, MACD, SMA, Bollinger Bands) to signal scoring and charts. Phase 12 added backtesting engine (replay signal generation over historical data, equity curves, trade logs, performance metrics). Phase 13 added stock search, profile/password management, mobile responsive sidebar, code splitting, and admin dashboard page. Phase 14 added realistic backtesting: transaction costs (commission + slippage), position sizing, stop-loss/take-profit exits, benchmark comparison (SPY with alpha/beta), backtest comparison view, and CSV export. Phase 15 added signal intelligence: component score breakdown visualization, expandable signal cards, accuracy deep-dive (trend + distribution), signal detail panel with outcomes and linked articles, methodology tab with adaptive weights display. Post-phase work added ticker extraction improvements, sector filtering, and deployment fixes.

### What's implemented
- FastAPI backend with JWT auth (register/login/refresh/me/profile/password)
- Stock listing with sector filter, search, pagination
- Sectors API: dynamic sector list from DB (`/api/stocks/sectors`)
- 6 stock sectors: Energy, Financials, Technology, Communication Services, Consumer Discretionary, Market ETFs (~86 tickers)
- Watchlist CRUD
- Market data pipeline: yfinance → Postgres (hourly via Celery, weekdays at :05)
- Historical data seeding: full available history (~30+ years) via `make seed-history`
- News scraping pipeline: 7 sources (Yahoo Finance, Finviz, Reuters RSS, SEC EDGAR, MarketWatch, Reddit, FRED)
- Scraper orchestration: Celery group fans out all scrapers hourly at :00, chains sentiment processing
- Ticker extraction: $TICKER patterns (0.95), parenthetical (AAPL) (0.90), ALL-CAPS matching (0.70), company name matching (0.60)
- Articles API with pagination, source/ticker/status filtering
- FinBERT sentiment analysis: singleton model, batch inference, 512-token chunking, lazy-loaded on compute VM
- Sentiment API: per-ticker timeline, scored articles, sector summaries, trending stocks
- Sentiment pipeline: auto-processes new articles after scraping + :15 catch-up task
- Signal generation: 6-component composite scoring (sentiment momentum 30%, sentiment volume 20%, price momentum 15%, volume anomaly 10%, RSI 15%, trend 10%)
- Signal API: paginated list with direction/strength/ticker/sector filters, per-ticker history, latest signals feed, signal detail with outcomes + linked articles, accuracy trend + distribution endpoints
- Alert dispatch: Discord webhooks + SMTP email, per-user AlertConfig matching, AlertLog history
- Alert API: config CRUD, alert history, test alert endpoint
- Admin API: trigger scrape, historical seed, maintenance, DB stats
- React frontend with AppLayout (sidebar + header), login/register, dark mode (default dark, persists on refresh)
- Mobile responsive sidebar: collapsible drawer on small screens with hamburger toggle
- Dynamic sidebar with sector links fetched from API, clickable to filtered signals view
- Stock search: type-ahead search bar in header with debounced dropdown, navigates to stock detail
- TradingView Lightweight Charts: candlestick price chart + volume histogram + indicator overlays (SMA, Bollinger Bands) + RSI/MACD sub-charts
- Sentiment UI: SentimentBadge, SentimentChart, SentimentPage (clickable sector cards + trending tickers)
- Signal UI: expandable SignalCard with component breakdown bars, SignalsPage with 3 tabs (Signals/Accuracy/Methodology), signal detail panel with outcomes + linked articles, AlertsPage (config CRUD + history)
- StockDetailPage with price/volume charts, indicator toggles (SMA, Bollinger, RSI, MACD), sentiment chart, signal history, signal accuracy, watchlist toggle
- Dashboard: signals feed (10 latest moderate+), clickable sector sentiment heatmap, top movers (bullish/bearish), article activity chart
- Settings page: profile editing (username/email), password change, dark mode toggle, notification info
- Admin page: task triggers (scrape, seed, maintenance, outcomes, weights), database stats table
- Watchlist: sparkline charts (30-day price via TradingView), signal direction badges, links to stock detail
- UI polish: loading skeletons, error retry buttons, consistent empty states
- SQLAlchemy models for all 15 tables
- Docker Compose with resource limits, health checks, non-root users, tini init
- Nginx reverse proxy with SSL/TLS (Let's Encrypt), HSTS, CSP, security headers
- Nginx auth rate limiting: 5 req/min per IP on `/api/auth/` (brute-force protection)
- Password complexity: min 8 chars, uppercase + lowercase + digit required
- Username validation: 3-50 characters
- Pagination bounds: all endpoints enforce `per_page` max 100
- Certbot auto-renewal service
- Structured JSON logging with request ID correlation (FastAPI + Celery)
- Enhanced health endpoint: DB + Redis connectivity checks, `?detail=true` mode
- Configurable DB pool (pool_size, max_overflow via env vars)
- Celery explicit task include (not autodiscover) for reliable task registration
- Celery task routing: 5 queues (default, scraping, sentiment, signals, maintenance)
- Celery task reliability: `task_acks_late`, `task_reject_on_worker_lost`
- Celery graceful shutdown with systemd TimeoutStopSec
- asyncpg connection safety: engine.dispose() in run_async() to prevent cross-loop issues
- Alembic initial migration (13 tables)
- Database backup/restore scripts with retention
- Flower (Celery monitoring) on :5555 (SSH tunnel access)
- GitHub Actions CI: lint, test, Docker build
- 9 performance indexes (sentiment_scores, articles, signals, market_data, etc.)
- Data retention: article text compression, scrape/alert log cleanup, weak signal purge
- Daily sentiment materialized view with hourly refresh
- Admin: maintenance trigger + DB stats (row counts, table sizes)
- Configurable retention periods via env vars (article text 90d, logs 30d, signals 180d)
- Signal feedback loop: outcome evaluation (1/3/5-day windows), adaptive per-sector weight optimization, accuracy metrics API
- Technical indicators: RSI (Wilder's 14-period), SMA (20/50), EMA, MACD (12/26/9), Bollinger Bands — pure-Python computation module
- Indicators API: on-the-fly computation from stored OHLCV data (no extra DB table)
- Backtesting engine: replay signal generation over historical OHLCV data (technical mode) or OHLCV + sentiment (full mode)
- Backtest modes: "technical" (OHLCV-only, full 30+ year range) and "full" (all 6 components, limited to sentiment data availability)
- Backtest metrics: total/annualized return, Sharpe ratio, max drawdown, win rate, avg win/loss, best/worst trade
- Backtest transaction costs: configurable commission % + slippage % on buy/sell
- Backtest position sizing: invest configurable % of cash (10-100%) per trade
- Backtest risk management: stop-loss and take-profit exit rules with configurable thresholds
- Backtest benchmark comparison: auto-compare vs SPY (or custom ticker) with alpha, beta, benchmark equity curve overlay
- Backtest comparison view: side-by-side metrics + overlaid normalized equity curves for two backtests
- Backtest CSV export: download equity curve or trade log as CSV
- Backtest API: create + queue (Celery), list (paginated), detail with equity curve + trades, delete (cascade), CSV export
- Backtest frontend: configuration form (stock/sector, date range, mode, capital, strength, advanced settings), result cards, equity curve chart with benchmark overlay, metrics grid with benchmark row, trade log with exit reason badges, comparison mode
- Code splitting: React.lazy + Suspense for all route pages, Vite auto chunk splitting
- Unit tests: ticker extraction, text cleaning, scraper parsers, sentiment, signal scoring, signal intelligence (schemas, accuracy computation, bucketing), indicators, feedback, backtester (costs, sizing, stop-loss, benchmark), market data, maintenance, password validation, secret key (264 tests)

### What's next
- Phase 15: TBD

## Architecture

Two Oracle Cloud free-tier ARM VMs:

- **Docker VM**: Postgres 16, Redis 7, FastAPI backend, React frontend, Nginx reverse proxy (all containers via `docker-compose.yml`)
- **Compute VM** (2 cores, 12GB RAM): Celery workers + FinBERT model. Connects to Postgres/Redis on Docker VM over Oracle internal VPC.

## Project Structure

```
backend/           Python backend (FastAPI + Celery + SQLAlchemy)
  app/             FastAPI application
    api/           Route handlers: auth, stocks, watchlist, market_data, articles, sentiment, signals, alerts, backtests, admin (+ health)
    core/          Security (JWT/bcrypt), structured logging, request middleware, exceptions
    models/        SQLAlchemy ORM models (15 tables)
    schemas/       Pydantic request/response schemas (auth, stock, watchlist, market_data, article, sentiment, signal, alert, backtest, common)

  worker/          Celery application
    celery_app.py  Celery instance + Redis config
    beat_schedule  Cron schedule (:00 scrape, :05 market data, :15 sentiment, :30 signals, :35 matview refresh, :45 outcomes, 3AM maintenance, 4AM weights)
    tasks/         Task modules: scraping/, sentiment/, signals/ (generator, dispatcher, outcome evaluator, weight optimizer, backtest), maintenance/ (retention + matview refresh)
    utils/         Rate limiter, text cleaner, ticker extractor, async_task helper, technical_indicators, backtester
  alembic/         Database migrations
  tests/           pytest test suite (264 tests)
frontend/          React 19 + TypeScript (Vite, Tailwind)
  src/api/         Axios API client (auth, stocks, watchlist, marketData, articles, sentiment, signals, alerts, backtests, admin)
  src/components/  Layout (AppLayout, Header, Sidebar, SearchBar), Charts (PriceChart, VolumeChart, SentimentChart, SparklineChart, RSIChart, MACDChart, EquityCurveChart), Forms (BacktestForm), Backtests (BacktestResultCard, MetricsSummary, TradeLog, BacktestCompare), Sentiment (SentimentBadge), Signals (SignalCard, ComponentBreakdown, SignalDetailPanel, AccuracyTrendChart, AccuracyDistributionChart, WeightsTable, AccuracyBadge), Dashboard (SectorHeatmapCard, TopMoversCard, ArticleActivityCard, AccuracyCard), Common (LoadingSkeleton, ErrorRetry, Card)
  src/constants/   Shared UI constants (DIRECTION_COLORS, STRENGTH_STYLES)
  src/pages/       All route pages (Dashboard, StockDetail, Sentiment, Signals, Backtest, Alerts, Admin, Login, Register, Settings)
  src/store/       Zustand state stores (auth, theme, sidebar)
  src/types/       TypeScript interfaces
  src/utils/       Shared utilities (formatTimeAgo, humanizeSource)
nginx/             Reverse proxy config (SSL/TLS template with envsubst)
scripts/           backup, restore, setup scripts
deploy/            Systemd units and env templates for VMs (celery-worker.service, celery-beat.service)
docs/              Architecture, deployment, API reference, data sources
```

## Commands

### Development
```bash
make up                    # Start all Docker services
make down                  # Stop all services
make build                 # Build all Docker images
make logs                  # Tail all service logs
make logs-backend          # Tail backend logs only
make migrate               # Run alembic migrations (via Docker)
make seed                  # Seed S&P 500 stocks
make seed-history          # Seed full historical market data (max available)
make seed-all              # Seed stocks + historical data in one go
make test                  # Run backend pytest suite
make lint                  # Run ruff check + format
make health                # Check health endpoint with details
make dev-backend           # Run FastAPI with hot reload (local)
make dev-frontend          # Run Vite dev server (local)
```

### Operations
```bash
make backup                # Run database backup with retention
make restore FILE=<path>   # Restore database from backup
make certbot DOMAIN=<dom>  # Obtain SSL cert via Let's Encrypt
```

### Backend CLI
```bash
cd backend
uvicorn app.main:app --reload --port 8000          # Run API server
alembic revision --autogenerate -m "description"    # Create migration
alembic upgrade head                                 # Apply migrations
python -m scripts.seed_sp500                         # Seed stock data
python -m scripts.seed_historical_data               # Seed full price history
python -m scripts.seed_historical_data --period 5y   # Seed 5 years only
python -m pytest tests/ -v                           # Run tests
```

### Celery (on compute VM)
```bash
# Managed by systemd (celery-worker.service, celery-beat.service)
sudo systemctl restart celery-worker celery-beat
sudo journalctl -u celery-worker -f              # Watch worker logs
sudo journalctl -u celery-beat -f                 # Watch beat logs

# Manual task triggers
cd /opt/stock-predictor/backend
.venv/bin/celery -A worker.celery_app call worker.tasks.scraping.orchestrate_scraping --queue scraping
.venv/bin/celery -A worker.celery_app call worker.tasks.sentiment.sentiment_task.process_new_articles_sentiment --queue sentiment
.venv/bin/celery -A worker.celery_app call worker.tasks.signals.signal_generator.generate_all_signals --queue signals
```

## Code Conventions

### Python (backend/)
- Python 3.11+, type hints everywhere
- Async SQLAlchemy with `asyncpg` driver
- Pydantic v2 for all schemas, `from_attributes = True` for ORM models
- FastAPI dependency injection for DB sessions and auth
- Ruff for linting and formatting (line length 120)
- Models use SQLAlchemy 2.0 `Mapped` / `mapped_column` syntax
- Tests use pytest-asyncio with `auto` mode
- Celery tasks bridge async/sync via `run_async()` helper (`worker/utils/async_task.py`)
- Shared `PaginationMeta` and `calc_total_pages()` in `schemas/common.py`
- Shared `get_stock_by_ticker()` dependency in `dependencies.py`

### TypeScript (frontend/)
- React 19 + TypeScript strict mode
- Vite for build tooling with automatic code splitting (React.lazy + Suspense)
- Zustand for client state (auth with persist, theme with persist, sidebar)
- TanStack Query for server state (caching, pagination)
- Tailwind CSS for styling with dark mode (`class` strategy)
- TradingView Lightweight Charts for financial charts
- Path alias: `@/` maps to `src/`

### Database
- Postgres 16, all timestamps with timezone (`TIMESTAMPTZ`)
- Alembic for migrations — never modify tables directly
- Naming: snake_case tables and columns
- Unique constraints for deduplication (article URLs, stock+date pairs)

### API Patterns
- All routes under `/api/` prefix
- JWT Bearer auth on protected endpoints via `get_current_user` dependency
- Admin-only endpoints via `get_current_admin` dependency
- Pagination: `PaginatedStocks` / `PaginatedArticles` / `PaginatedSentiment` / `PaginatedSignals` / `PaginatedAlertLogs` with `data` + `meta`
- OAuth2 form login at `/api/auth/login` (username field = email)
- 201 for creates, 204 for deletes, standard HTTP error codes

### Secrets
- ALL secrets in `.env` files, loaded via `pydantic-settings`
- Never hardcode IPs, passwords, API keys, or webhook URLs
- `.gitignore` blocks `.env`, `*.pem`, `*.key`, model binaries
- `detect-secrets` pre-commit hook catches accidental leaks
- Postgres/Redis only accessible on internal VPC network

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/config.py` | Central config — all env vars loaded here via pydantic-settings |
| `backend/app/database.py` | SQLAlchemy async engine, session factory, Base |
| `backend/app/main.py` | FastAPI app factory, CORS, lifespan |
| `backend/app/dependencies.py` | `get_db`, `get_current_user`, `get_current_admin`, `get_stock_by_ticker` |
| `backend/app/core/security.py` | JWT create/verify, bcrypt password hashing |
| `backend/app/core/logging_config.py` | JSONFormatter, setup_logging(), request_id_var ContextVar |
| `backend/app/core/middleware.py` | RequestLoggingMiddleware — request timing + correlation IDs |
| `backend/app/api/health.py` | Health endpoint with DB + Redis checks, `?detail=true` |
| `backend/app/api/router.py` | Aggregates all sub-routers under `/api` |
| `backend/app/api/auth.py` | Register, login, refresh, me, profile update, password change |
| `backend/app/api/stocks.py` | Stock list (paginated, filterable) and detail |
| `backend/app/api/watchlist.py` | Watchlist CRUD |
| `backend/app/api/market_data.py` | Daily + intraday OHLCV + indicators endpoints |
| `backend/app/api/articles.py` | Article list (paginated, filterable by source/ticker) + sources |
| `backend/app/api/sentiment.py` | Sentiment endpoints: timeline, articles, sectors, trending |
| `backend/app/api/signals.py` | Signal endpoints: list (filtered), per-ticker history, latest feed, accuracy (summary/trend/distribution), detail (outcomes + linked articles), weights |
| `backend/app/api/alerts.py` | Alert endpoints: config CRUD, history, test alert |
| `backend/app/api/admin.py` | Admin: trigger scrape, seed historical, maintenance trigger, DB stats |
| `backend/worker/celery_app.py` | Celery instance, task routing, explicit task include |
| `backend/worker/tasks/maintenance/retention.py` | Reusable batched delete/nullify utilities for data retention |
| `backend/worker/tasks/maintenance/tasks.py` | Maintenance tasks: article compression, log cleanup, matview refresh |
| `backend/worker/beat_schedule.py` | Cron schedule for all tasks (scrape, market, sentiment, signals, maintenance) |
| `backend/worker/tasks/scraping/orchestrate.py` | Fan-out all 7 scrapers via Celery group → chain sentiment |
| `backend/worker/tasks/sentiment/finbert_analyzer.py` | Singleton FinBERT model: batch inference, chunking, lazy-loaded |
| `backend/worker/tasks/sentiment/sentiment_task.py` | Celery task: process unprocessed articles through FinBERT |
| `backend/worker/tasks/signals/signal_generator.py` | Celery task: 6-component composite signal scoring for all active stocks |
| `backend/worker/tasks/signals/alert_dispatcher.py` | Celery task: match signals to AlertConfigs, send Discord/email |
| `backend/worker/tasks/signals/outcome_evaluator.py` | Celery task: evaluate signal accuracy after 1/3/5 day windows |
| `backend/worker/tasks/signals/weight_optimizer.py` | Celery task: compute per-sector adaptive weights from outcomes |
| `backend/worker/utils/technical_indicators.py` | Pure computation: RSI, SMA, EMA, MACD, Bollinger Bands |
| `backend/worker/utils/backtester.py` | Pure backtesting engine: signal replay, trading simulation, performance metrics |
| `backend/worker/tasks/signals/backtest_task.py` | Celery task: fetch data, run backtester, store results |
| `backend/app/api/backtests.py` | Backtest endpoints: create, list, detail, delete, CSV export |
| `backend/app/models/backtest.py` | Backtest + BacktestTrade ORM models |
| `backend/worker/tasks/scraping/base_scraper.py` | Abstract scraper with DB storage, dedup, ticker + company name extraction |
| `backend/worker/tasks/scraping/market_data.py` | yfinance fetch + historical seed task |
| `backend/scripts/seed_sp500.py` | Seed 6 sectors (~86 tickers): Energy, Financials, Technology, Comm Services, Consumer Disc, ETFs |
| `backend/scripts/seed_historical_data.py` | Backfill full OHLCV history for all tickers |
| `backend/alembic/versions/001_initial_schema.py` | Initial migration: all 13 tables |
| `backend/alembic/versions/002_backtesting_v2.py` | Backtest v2: transaction costs, position sizing, stop-loss/take-profit, benchmark columns |
| `backend/alembic/versions/003_signal_intelligence.py` | Signal intelligence: add sentiment_volume_score column |
| `scripts/backup.sh` | Database backup with configurable retention |
| `scripts/restore.sh` | Database restore from backup |
| `.github/workflows/ci.yml` | CI pipeline: lint, test, Docker build |
| `docker-compose.yml` | All Docker VM services (hardened with resource limits, health checks, Flower) |
| `frontend/src/App.tsx` | React Router with lazy-loaded routes, protected + admin routes |
| `frontend/src/store/authStore.ts` | Zustand auth state with localStorage persist (includes is_admin) |
| `frontend/src/components/layout/SearchBar.tsx` | Stock search with debounced dropdown |
| `frontend/src/pages/AdminPage.tsx` | Admin dashboard: task triggers + DB stats |

## API Endpoints (implemented)

| Method | Path | Auth | Status |
|--------|------|------|--------|
| GET | `/api/health` | No | Done |
| POST | `/api/auth/register` | No | Done |
| POST | `/api/auth/login` | No | Done |
| POST | `/api/auth/refresh` | No | Done |
| GET | `/api/auth/me` | Yes | Done |
| PUT | `/api/auth/profile` | Yes | Done |
| PUT | `/api/auth/password` | Yes | Done |
| GET | `/api/stocks` | Yes | Done |
| GET | `/api/stocks/sectors` | Yes | Done |
| GET | `/api/stocks/{ticker}` | Yes | Done |
| GET | `/api/watchlist` | Yes | Done |
| POST | `/api/watchlist` | Yes | Done |
| DELETE | `/api/watchlist/{ticker}` | Yes | Done |
| GET | `/api/market-data/{ticker}/daily` | Yes | Done |
| GET | `/api/market-data/{ticker}/intraday` | Yes | Done |
| GET | `/api/market-data/{ticker}/indicators` | Yes | Done |
| GET | `/api/articles` | Yes | Done |
| GET | `/api/articles/sources` | Yes | Done |
| GET | `/api/sentiment/{ticker}` | Yes | Done |
| GET | `/api/sentiment/{ticker}/articles` | Yes | Done |
| GET | `/api/sentiment/summary/sectors` | Yes | Done |
| GET | `/api/sentiment/trending/stocks` | Yes | Done |
| GET | `/api/signals` | Yes | Done |
| GET | `/api/signals/latest` | Yes | Done |
| GET | `/api/signals/accuracy` | Yes | Done |
| GET | `/api/signals/accuracy/{ticker}` | Yes | Done |
| GET | `/api/signals/accuracy/trend` | Yes | Done |
| GET | `/api/signals/accuracy/distribution` | Yes | Done |
| GET | `/api/signals/detail/{signal_id}` | Yes | Done |
| GET | `/api/signals/weights` | Yes | Done |
| GET | `/api/signals/{ticker}` | Yes | Done |
| GET | `/api/alerts/configs` | Yes | Done |
| POST | `/api/alerts/configs` | Yes | Done |
| PUT | `/api/alerts/configs/{id}` | Yes | Done |
| DELETE | `/api/alerts/configs/{id}` | Yes | Done |
| GET | `/api/alerts/history` | Yes | Done |
| POST | `/api/alerts/test` | Yes | Done |
| POST | `/api/backtests` | Yes | Done |
| GET | `/api/backtests` | Yes | Done |
| GET | `/api/backtests/{id}` | Yes | Done |
| DELETE | `/api/backtests/{id}` | Yes | Done |
| GET | `/api/backtests/{id}/export` | Yes | Done |
| POST | `/api/admin/seed-history` | Admin | Done |
| POST | `/api/admin/scrape-now` | Admin | Done |
| POST | `/api/admin/maintenance` | Admin | Done |
| POST | `/api/admin/evaluate-outcomes` | Admin | Done |
| POST | `/api/admin/compute-weights` | Admin | Done |
| GET | `/api/admin/db-stats` | Admin | Done |

## Data Pipeline

```
Initialization:
  make seed-all → seed 6 sectors (~86 tickers) + backfill full historical OHLCV (max available, ~30+ years)

Hourly (Celery Beat on Compute VM):
  :00 → fan-out 7 scrapers → store articles + extract tickers (symbol + company name matching) → chain FinBERT sentiment
  :05 → fetch market data via yfinance (5-day window, weekdays only)
  :15 → sentiment catch-up (process any unprocessed articles)
  :30 → generate composite signals → dispatch alerts (Discord + email) for moderate+ signals
  :35 → refresh materialized views (daily sentiment)

  :45 → evaluate signal outcomes (1/3/5-day windows)

Daily:
  3:00 AM → data maintenance (compress old articles, clean logs, purge weak signals)
  4:00 AM → compute adaptive signal weights (per-sector optimization from outcomes)
```

## Signal Scoring

```
composite = 0.30 * sentiment_momentum + 0.20 * sentiment_volume
          + 0.15 * price_momentum    + 0.10 * volume_anomaly
          + 0.15 * rsi_score         + 0.10 * trend_score

RSI score:   tanh((50 - rsi) / 50 * 2.5)  — oversold → positive, overbought → negative
Trend score: 0.6 * sma_crossover + 0.4 * macd_histogram_signal

Weights are adaptive: per-sector optimization runs daily at 4 AM based on outcome accuracy.

Strong: |score| > 0.6  |  Moderate: > 0.35  |  Weak: otherwise
```
