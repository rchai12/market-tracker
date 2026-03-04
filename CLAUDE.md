# Stock Predictor

Sentiment-driven stock market prediction system. Scrapes financial news, runs FinBERT sentiment analysis, correlates with market data, generates composite trading signals, and surfaces everything through a React dashboard with Discord/email alerts.

## Current Status

**Phase 2 complete.** Auth, stock listing, watchlist API, and frontend layout are built.

### What's implemented
- FastAPI backend with JWT auth (register/login/refresh/me)
- Stock listing with sector filter, search, pagination
- Watchlist CRUD
- React frontend with AppLayout (sidebar + header), login/register, dark mode
- Placeholder pages for all routes (dashboard, signals, sentiment, watchlist, alerts, settings)
- SQLAlchemy models for all 13 tables
- Celery app + beat schedule structure (tasks not yet implemented)
- Docker Compose, nginx, Dockerfiles
- Unit tests for JWT, password hashing, ticker extraction, text cleaning

### What's next
- Phase 3: Market data pipeline (yfinance + Celery + TradingView charts)
- Phase 4: News scraping pipeline (7 sources)
- Phase 5: FinBERT sentiment analysis
- Phase 6: Signal generation + alerts
- Phase 7: Dashboard polish
- Phase 8: Hardening + deployment
- Phase 9: Data retention + optimization

## Architecture

Two Oracle Cloud free-tier ARM VMs:

- **Docker VM**: Postgres 16, Redis 7, FastAPI backend, React frontend, Nginx reverse proxy (all containers via `docker-compose.yml`)
- **Compute VM** (2 cores, 12GB RAM): Celery workers + FinBERT model. Connects to Postgres/Redis on Docker VM over Oracle internal VPC.

## Project Structure

```
backend/           Python backend (FastAPI + Celery + SQLAlchemy)
  app/             FastAPI application
    api/           Route handlers: auth, stocks, watchlist (+ health)
    core/          Security (JWT/bcrypt), exceptions
    models/        SQLAlchemy ORM models (13 tables)
    schemas/       Pydantic request/response schemas
    services/      Business logic layer (placeholder)
  worker/          Celery application
    celery_app.py  Celery instance + Redis config
    beat_schedule  Hourly cron schedule
    tasks/         Task modules: scraping/, sentiment/, signals/
    utils/         Rate limiter, text cleaner, ticker extractor
  alembic/         Database migrations
  tests/           pytest test suite
frontend/          React 19 + TypeScript (Vite, Tailwind)
  src/api/         Axios API client (auth, stocks, watchlist)
  src/components/  Layout (AppLayout, Sidebar, Header)
  src/pages/       All route pages (Dashboard, Login, Register, etc.)
  src/store/       Zustand state stores (auth, theme)
  src/types/       TypeScript interfaces
nginx/             Reverse proxy config
scripts/           Seed data, setup scripts, health checks
deploy/            Systemd units and env templates for VMs
docs/              Architecture, deployment, API reference, data sources
```

## Commands

### Development
```bash
make up                    # Start all Docker services
make down                  # Stop all services
make logs                  # Tail all service logs
make migrate               # Run alembic migrations (via Docker)
make seed                  # Seed S&P 500 stocks
make test                  # Run backend pytest suite
make lint                  # Run ruff check + format
make dev-backend           # Run FastAPI with hot reload (local)
make dev-frontend          # Run Vite dev server (local)
```

### Backend CLI
```bash
cd backend
uvicorn app.main:app --reload --port 8000          # Run API server
alembic revision --autogenerate -m "description"    # Create migration
alembic upgrade head                                 # Apply migrations
python -m scripts.seed_sp500                         # Seed stock data
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
- Pagination: `PaginatedStocks` schema with `data` + `meta` (page, per_page, total, total_pages)
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
| `backend/app/dependencies.py` | `get_db`, `get_current_user`, `get_current_admin` |
| `backend/app/core/security.py` | JWT create/verify, bcrypt password hashing |
| `backend/app/api/router.py` | Aggregates all sub-routers under `/api` |
| `backend/app/api/auth.py` | Register, login, refresh, me endpoints |
| `backend/app/api/stocks.py` | Stock list (paginated, filterable) and detail |
| `backend/app/api/watchlist.py` | Watchlist CRUD |
| `backend/worker/celery_app.py` | Celery instance, task routing, autodiscovery |
| `backend/worker/beat_schedule.py` | Hourly cron schedule for all tasks |
| `docker-compose.yml` | All Docker VM services |
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

## Data Pipeline

```
Celery Beat (hourly at :00) → fan-out scrapers → store articles → FinBERT sentiment
Celery Beat (hourly at :05) → fetch market data via yfinance
Celery Beat (hourly at :30) → generate composite signals → dispatch alerts
```

## Signal Scoring

```
composite = 0.40 * sentiment_momentum + 0.25 * sentiment_volume
          + 0.20 * price_momentum    + 0.15 * volume_anomaly

Strong: |score| > 0.6  |  Moderate: > 0.35  |  Weak: otherwise
```
