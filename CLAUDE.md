# Stock Predictor

Sentiment-driven stock market prediction system. Scrapes financial news, runs FinBERT sentiment analysis, correlates with market data, generates composite trading signals, and surfaces everything through a React dashboard with Discord/email alerts.

## Current Status

**Phase 9 (data retention + optimization) complete.** All core features built through Phase 7. Phase 8 added hardening + deployment. Phase 9 added 9 missing indexes, data retention tasks (article compression, log cleanup), daily sentiment materialized view, admin maintenance/db-stats endpoints, and configurable retention periods.

### What's implemented
- FastAPI backend with JWT auth (register/login/refresh/me)
- Stock listing with sector filter, search, pagination
- Watchlist CRUD
- Market data pipeline: yfinance → Postgres (hourly via Celery, weekdays at :05)
- Historical data seeding: full available history (~30+ years) via `make seed-history`
- News scraping pipeline: 7 sources (Yahoo Finance, Finviz, Reuters RSS, SEC EDGAR, MarketWatch, Reddit, FRED)
- Scraper orchestration: Celery group fans out all scrapers hourly at :00, chains sentiment processing
- Articles API with pagination, source/ticker/status filtering
- FinBERT sentiment analysis: singleton model, batch inference, 512-token chunking, lazy-loaded on compute VM
- Sentiment API: per-ticker timeline, scored articles, sector summaries, trending stocks
- Sentiment pipeline: auto-processes new articles after scraping + :15 catch-up task
- Signal generation: composite scoring (sentiment momentum 40%, sentiment volume 25%, price momentum 20%, volume anomaly 15%)
- Signal API: paginated list with direction/strength/ticker filters, per-ticker history, latest signals feed
- Alert dispatch: Discord webhooks + SMTP email, per-user AlertConfig matching, AlertLog history
- Alert API: config CRUD, alert history, test alert endpoint
- Admin API: trigger scrape and historical seed on demand
- React frontend with AppLayout (sidebar + header), login/register, dark mode
- TradingView Lightweight Charts: candlestick price chart + volume histogram
- Sentiment UI: SentimentBadge, SentimentChart, SentimentPage (sector + trending), StockDetailPage integration
- Signal UI: SignalCard, SignalsPage (filtered grid), AlertsPage (config CRUD + history)
- StockDetailPage with price/volume charts, sentiment chart, signal history, watchlist toggle
- Dashboard: signals feed (10 latest moderate+), sector sentiment heatmap, top movers (bullish/bearish), article activity chart
- Settings page: profile display, dark mode toggle, notification info
- Watchlist: sparkline charts (30-day price via TradingView), signal direction badges, links to stock detail
- UI polish: loading skeletons, error retry buttons, consistent empty states
- SQLAlchemy models for all 13 tables
- Docker Compose with resource limits, health checks, non-root users, tini init
- Nginx reverse proxy with SSL/TLS (Let's Encrypt), HSTS, CSP, security headers
- Certbot auto-renewal service
- Structured JSON logging with request ID correlation (FastAPI + Celery)
- Enhanced health endpoint: DB + Redis connectivity checks, `?detail=true` mode
- Configurable DB pool (pool_size, max_overflow via env vars)
- Celery task reliability: `task_acks_late`, `task_reject_on_worker_lost`
- Celery graceful shutdown with systemd TimeoutStopSec
- Alembic initial migration (13 tables)
- Database backup/restore scripts with retention
- Flower (Celery monitoring) on :5555 (SSH tunnel access)
- GitHub Actions CI: lint, test, Docker build
- 9 performance indexes (sentiment_scores, articles, signals, market_data, etc.)
- Data retention: article text compression, scrape/alert log cleanup, weak signal purge
- Daily sentiment materialized view with hourly refresh
- Admin: maintenance trigger + DB stats (row counts, table sizes)
- Configurable retention periods via env vars (article text 90d, logs 30d, signals 180d)
- Unit tests for JWT, password hashing, ticker extraction, text cleaning, scraper parsers, sentiment, signal scoring, maintenance (75 tests)

### What's next
- Phase 10: TBD

## Architecture

Two Oracle Cloud free-tier ARM VMs:

- **Docker VM**: Postgres 16, Redis 7, FastAPI backend, React frontend, Nginx reverse proxy (all containers via `docker-compose.yml`)
- **Compute VM** (2 cores, 12GB RAM): Celery workers + FinBERT model. Connects to Postgres/Redis on Docker VM over Oracle internal VPC.

## Project Structure

```
backend/           Python backend (FastAPI + Celery + SQLAlchemy)
  app/             FastAPI application
    api/           Route handlers: auth, stocks, watchlist, market_data, articles, sentiment, signals, alerts, admin (+ health)
    core/          Security (JWT/bcrypt), structured logging, request middleware, exceptions
    models/        SQLAlchemy ORM models (13 tables)
    schemas/       Pydantic request/response schemas (auth, stock, watchlist, market_data, article, sentiment, signal, alert, common)
    services/      Business logic layer (placeholder)
  worker/          Celery application
    celery_app.py  Celery instance + Redis config
    beat_schedule  Cron schedule (:00 scrape, :05 market data, :15 sentiment, :30 signals, :35 matview refresh, 3AM maintenance)
    tasks/         Task modules: scraping/, sentiment/, signals/, maintenance/ (retention + matview refresh)
    utils/         Rate limiter, text cleaner, ticker extractor, async_task helper
  alembic/         Database migrations
  tests/           pytest test suite (62 tests)
frontend/          React 19 + TypeScript (Vite, Tailwind)
  src/api/         Axios API client (auth, stocks, watchlist, marketData, articles, sentiment, signals, alerts)
  src/components/  Layout, Charts (PriceChart, VolumeChart, SentimentChart, SparklineChart), Sentiment (SentimentBadge), Signals (SignalCard), Dashboard (SectorHeatmapCard, TopMoversCard, ArticleActivityCard), Common (LoadingSkeleton, ErrorRetry, Card)
  src/constants/   Shared UI constants (DIRECTION_COLORS, STRENGTH_STYLES)
  src/pages/       All route pages (Dashboard, StockDetail, Sentiment, Signals, Alerts, Login, Register, etc.)
  src/store/       Zustand state stores (auth, theme)
  src/types/       TypeScript interfaces
  src/utils/       Shared utilities (formatTimeAgo, humanizeSource)
nginx/             Reverse proxy config (SSL/TLS template with envsubst)
scripts/           seed_sp500, seed_historical_data, backup, restore, setup scripts
deploy/            Systemd units and env templates for VMs
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
celery -A worker.celery_app worker --loglevel=info --concurrency=2
celery -A worker.celery_app beat --loglevel=info
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
- Vite for build tooling
- Zustand for client state (auth with persist, theme with persist)
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
| `backend/app/api/auth.py` | Register, login, refresh, me endpoints |
| `backend/app/api/stocks.py` | Stock list (paginated, filterable) and detail |
| `backend/app/api/watchlist.py` | Watchlist CRUD |
| `backend/app/api/market_data.py` | Daily + intraday OHLCV endpoints |
| `backend/app/api/articles.py` | Article list (paginated, filterable by source/ticker) + sources |
| `backend/app/api/sentiment.py` | Sentiment endpoints: timeline, articles, sectors, trending |
| `backend/app/api/signals.py` | Signal endpoints: list (filtered), per-ticker history, latest feed |
| `backend/app/api/alerts.py` | Alert endpoints: config CRUD, history, test alert |
| `backend/app/api/admin.py` | Admin: trigger scrape, seed historical, maintenance trigger, DB stats |
| `backend/worker/celery_app.py` | Celery instance, task routing, autodiscovery |
| `backend/worker/tasks/maintenance/retention.py` | Reusable batched delete/nullify utilities for data retention |
| `backend/worker/tasks/maintenance/tasks.py` | Maintenance tasks: article compression, log cleanup, matview refresh |
| `backend/worker/beat_schedule.py` | Cron schedule for all tasks (scrape, market, sentiment, signals, maintenance) |
| `backend/worker/tasks/scraping/orchestrate.py` | Fan-out all 7 scrapers via Celery group → chain sentiment |
| `backend/worker/tasks/sentiment/finbert_analyzer.py` | Singleton FinBERT model: batch inference, chunking, lazy-loaded |
| `backend/worker/tasks/sentiment/sentiment_task.py` | Celery task: process unprocessed articles through FinBERT |
| `backend/worker/tasks/signals/signal_generator.py` | Celery task: composite signal scoring for all active stocks |
| `backend/worker/tasks/signals/alert_dispatcher.py` | Celery task: match signals to AlertConfigs, send Discord/email |
| `backend/worker/tasks/scraping/base_scraper.py` | Abstract scraper with DB storage, dedup, ticker extraction |
| `backend/worker/tasks/scraping/market_data.py` | yfinance fetch + historical seed task |
| `scripts/seed_sp500.py` | Seed Energy + Financials tickers |
| `scripts/seed_historical_data.py` | Backfill full OHLCV history for all tickers |
| `backend/alembic/versions/001_initial_schema.py` | Initial migration: all 13 tables |
| `scripts/backup.sh` | Database backup with configurable retention |
| `scripts/restore.sh` | Database restore from backup |
| `.github/workflows/ci.yml` | CI pipeline: lint, test, Docker build |
| `docker-compose.yml` | All Docker VM services (hardened with resource limits, health checks, Flower) |
| `frontend/src/App.tsx` | React Router with protected routes + AppLayout |
| `frontend/src/store/authStore.ts` | Zustand auth state with localStorage persist |

## API Endpoints (implemented)

| Method | Path | Auth | Status |
|--------|------|------|--------|
| GET | `/api/health` | No | Done |
| POST | `/api/auth/register` | No | Done |
| POST | `/api/auth/login` | No | Done |
| POST | `/api/auth/refresh` | No | Done |
| GET | `/api/auth/me` | Yes | Done |
| GET | `/api/stocks` | Yes | Done |
| GET | `/api/stocks/{ticker}` | Yes | Done |
| GET | `/api/watchlist` | Yes | Done |
| POST | `/api/watchlist` | Yes | Done |
| DELETE | `/api/watchlist/{ticker}` | Yes | Done |
| GET | `/api/market-data/{ticker}/daily` | Yes | Done |
| GET | `/api/market-data/{ticker}/intraday` | Yes | Done |
| GET | `/api/articles` | Yes | Done |
| GET | `/api/articles/sources` | Yes | Done |
| GET | `/api/sentiment/{ticker}` | Yes | Done |
| GET | `/api/sentiment/{ticker}/articles` | Yes | Done |
| GET | `/api/sentiment/summary/sectors` | Yes | Done |
| GET | `/api/sentiment/trending/stocks` | Yes | Done |
| GET | `/api/signals` | Yes | Done |
| GET | `/api/signals/latest` | Yes | Done |
| GET | `/api/signals/{ticker}` | Yes | Done |
| GET | `/api/alerts/configs` | Yes | Done |
| POST | `/api/alerts/configs` | Yes | Done |
| PUT | `/api/alerts/configs/{id}` | Yes | Done |
| DELETE | `/api/alerts/configs/{id}` | Yes | Done |
| GET | `/api/alerts/history` | Yes | Done |
| POST | `/api/alerts/test` | Yes | Done |
| POST | `/api/admin/seed-history` | Admin | Done |
| POST | `/api/admin/scrape-now` | Admin | Done |
| POST | `/api/admin/maintenance` | Admin | Done |
| GET | `/api/admin/db-stats` | Admin | Done |

## Data Pipeline

```
Initialization:
  make seed-all → seed tickers + backfill full historical OHLCV (max available, ~30+ years)

Hourly:
  Celery Beat (:00) → fan-out 7 scrapers → store articles + extract tickers → FinBERT sentiment analysis
  Celery Beat (:05, weekdays) → fetch market data via yfinance (5-day window)
  Celery Beat (:15) → sentiment catch-up (process any unprocessed articles)
  Celery Beat (:30) → generate composite signals → dispatch alerts (Discord + email) for moderate+ signals
```

## Signal Scoring

```
composite = 0.40 * sentiment_momentum + 0.25 * sentiment_volume
          + 0.20 * price_momentum    + 0.15 * volume_anomaly

Strong: |score| > 0.6  |  Moderate: > 0.35  |  Weak: otherwise
```
