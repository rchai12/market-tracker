# Market Tracker

A sentiment-driven stock market prediction system that scrapes financial news, runs FinBERT sentiment analysis, correlates with market data, and generates composite trading signals with Discord/email alerts.

## Features

### Data Pipeline
- **News Scraping**: Hourly ingestion from 7 sources (Yahoo Finance, Finviz, Reuters RSS, SEC EDGAR, MarketWatch, Reddit, FRED)
- **Historical Data**: Full available price history (~30+ years) seeded on initialization via yfinance
- **Ticker Extraction**: 4-tier confidence scoring ($TICKER 0.95, parenthetical 0.90, ALL-CAPS 0.70, company name 0.60)
- **Sentiment Analysis**: FinBERT model scores every article as bullish/bearish/neutral with 512-token chunking
- **Event Classification**: Rule-based classifier for 10 categories (earnings, M&A, regulatory, product, analyst, insider, macro, legal, dividend, general)
- **Duplicate Detection**: Fuzzy title matching via rapidfuzz across sources within 24h windows
- **Article Quality Scoring**: 0–1 score from source credibility, quantitative content, ticker confidence, and article length
- **Options Flow**: yfinance options chain data (P/C ratio, IV skew, volume/OI), CBOE market-wide P/C ratio

### Signal Generation
- **7-Component Scoring**: Sentiment momentum, sentiment volume, price momentum, volume anomaly, options flow — each weighted adaptively per sector
- **Regime Multiplier**: RSI and trend act as context (not additive components) — dampen or boost the composite score by ±15% based on overbought/oversold/trending conditions
- **Market Regime Labels**: Each signal tagged with `trending_up`, `trending_down`, `overbought`, `oversold`, or `sideways`
- **Earnings Surprise**: yfinance EPS beat/miss data — 48h gated signal scored via `tanh(surprise_pct / 5.0)`
- **LLM Extraction**: Gemini Flash extracts `guidance_change` (raised/lowered/maintained) and `management_tone` (confident/cautious/neutral) from earnings articles
- **ML Ensemble**: Per-sector LightGBM classifier trained on component scores → `ml_score`, `ml_direction`, `ml_confidence` alongside rule-based scoring
- **Adaptive Weights**: Daily per-sector weight optimization from outcome feedback (1/3/5-day windows)
- **Source Credibility**: SEC EDGAR (1.0) > Reuters (0.9) > MarketWatch (0.7) > Reddit (0.4) weighting in sentiment momentum

### Infrastructure
- **Redis Caching**: `@cached()` decorator on 5 high-traffic endpoints with SCAN-based invalidation
- **Dead Letter Queue**: Failed Celery tasks captured to DB with admin retry UI
- **API Key Authentication**: SHA-256 hashed keys (`sp_` + 32 hex), dual JWT + API key auth
- **Admin Audit Logging**: All admin actions recorded with user/action/resource/IP
- **Health Monitoring**: DB/Redis/queue depth checks every 5 min → Discord webhook alerts
- **Slow Query Detection**: SQLAlchemy event listeners log queries exceeding 500ms threshold

### Frontend
- **React Dashboard**: TradingView Lightweight Charts with candlestick, volume, SMA, Bollinger Bands, RSI/MACD sub-charts
- **Signal Cards**: Expandable cards with predictive component breakdown bars + regime context section
- **Signal Intelligence**: Detail panel with outcomes + linked articles, accuracy trend/distribution charts, methodology tab with adaptive weights
- **Stock Detail**: Price/volume charts, indicator toggles, sentiment timeline, signal history, options section with P/C ratio chart
- **Backtesting**: Full backtest UI — configuration, equity curve with benchmark overlay, trade log, comparison mode, CSV export
- **Admin Dashboard**: Task triggers, DB stats, ML model status, task failure retry, audit log
- **Settings**: Profile editing, password change, dark mode, API key management (create/list/revoke)
- **Mobile Responsive**: Collapsible sidebar drawer with hamburger toggle

### Reliability & Security
- **JWT Authentication** with refresh tokens, profile/password management
- **Password Complexity**: Min 8 chars, uppercase + lowercase + digit required
- **Nginx Rate Limiting**: 5 req/min per IP on `/api/auth/` (brute-force protection)
- **Pagination Bounds**: All list endpoints enforce `per_page` max 100
- **SSL/TLS**: Let's Encrypt with HSTS, CSP, and security headers via Nginx
- **Comprehensive Tests**: 553 unit tests + 34 integration tests + 10 Playwright E2E tests, coverage enforcement (60% floor)

## Architecture

Runs on two Oracle Cloud free-tier ARM VMs:

| VM | Role | Services |
|----|------|----------|
| Docker VM | Application hosting | Postgres 16, Redis 7, FastAPI, React, Nginx |
| Compute VM | Data processing | Celery workers (2 cores), FinBERT model (12GB RAM) |

## Signal Scoring

```
composite = 0.40 * sentiment_momentum + 0.25 * sentiment_volume
          + 0.20 * price_momentum    + 0.15 * volume_anomaly
          + 0.10 * earnings_score   (when EARNINGS_ENABLED, weights scale proportionally)
          + 0.08 * options_score    (when OPTIONS_FLOW_ENABLED, weights scale proportionally)

composite, regime = apply_regime_multiplier(composite, rsi_score, trend_score)
  — RSI extreme (|rsi| > 0.4) → dampen 15%, regime = overbought/oversold
  — Strong trend confirming signal → boost 15%, regime = trending_up/down
  — Strong trend opposing signal  → dampen 15%
  — Default: regime = sideways

Strong: |score| > 0.6  |  Moderate: > 0.35  |  Weak: otherwise

Weights adapt daily via per-sector outcome optimization (1/3/5-day windows).
```

## Data Pipeline Schedule (Celery Beat)

```
Every 5 min:   Health check → Discord webhook if unhealthy
:00  Scrape 7 sources → store articles → chain FinBERT sentiment
:05  Fetch market data via yfinance (weekdays)
:10  Fetch options chain via yfinance (weekdays, if OPTIONS_FLOW_ENABLED)
:12  Fetch CBOE put/call ratio (weekdays, if OPTIONS_FLOW_ENABLED)
:15  Sentiment catch-up (process any unprocessed articles)
:20  LLM extraction (Gemini Flash on earnings articles, if LLM_EXTRACTION_ENABLED)
:30  Generate composite signals + ML inference → dispatch alerts
:35  Refresh materialized views
:45  Evaluate signal outcomes (1/3/5-day windows)
3AM  Data maintenance (compress old articles, clean logs, purge weak signals)
4AM  Compute adaptive signal weights per sector
4:30 Train ML models per sector (if ML_ENSEMBLE_ENABLED)
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Node.js 20+

### Setup

```bash
git clone <repo-url> market-tracker
cd market-tracker

# Create environment files
cp deploy/docker-vm/.env.docker.example .env
cp deploy/compute-vm/.env.compute.example backend/.env
# Edit both .env files with your actual values

# Start services
make up

# Run database migrations
make migrate

# Seed stocks AND backfill full price history (~30+ years per ticker)
make seed-all

# Verify
curl http://localhost/api/health
```

### Development

```bash
make dev-backend    # FastAPI with hot reload
make dev-frontend   # Vite dev server
make test           # Run backend pytest suite
make test-cov       # Tests with coverage report
make lint           # ruff check + format
```

## Tech Stack

### Backend
- **FastAPI** — async Python web framework
- **SQLAlchemy 2.0** — async ORM with PostgreSQL (asyncpg)
- **Celery + Redis** — distributed task queue with 5 named queues
- **FinBERT** — financial sentiment analysis (HuggingFace Transformers)
- **LightGBM** — per-sector ML signal ensemble classifier
- **yfinance** — market data (OHLCV, options chains, earnings)
- **google-genai** — Gemini Flash for LLM extraction
- **Alembic** — database migrations (12 versions)
- **rapidfuzz** — fuzzy duplicate detection

### Frontend
- **React 19** + TypeScript (strict mode)
- **Vite** — build tooling with code splitting (React.lazy + Suspense)
- **TanStack Query** — server state management with caching
- **Zustand** — client state (auth, theme, sidebar)
- **TradingView Lightweight Charts** — financial charting
- **Tailwind CSS** — dark mode styling

### Infrastructure
- **PostgreSQL 16** — primary database (21 tables)
- **Redis 7** — Celery broker + response cache
- **Nginx** — reverse proxy, SSL/TLS, rate limiting
- **Docker Compose** — container orchestration with resource limits and health checks

## Project Structure

```
backend/
  app/api/         Route handlers (auth, stocks, watchlist, market_data, articles,
                   sentiment, signals, alerts, backtests, admin, api_keys, health)
  app/models/      SQLAlchemy ORM (21 tables)
  app/schemas/     Pydantic request/response schemas
  app/core/        Security, caching, audit logging, slow query detection, middleware
  worker/tasks/
    scraping/      7 scrapers + orchestrator + market data + options data
    sentiment/     FinBERT analyzer + sentiment task + LLM extraction task
    signals/       Signal generator + component scores + alert dispatcher +
                   outcome evaluator + weight optimizer + ML trainer + backtest task
    maintenance/   Retention, matview refresh, health check
  worker/utils/    Ticker extractor, event classifier, duplicate detector,
                   technical indicators, ML trainer, backtester/, llm_extractor
  alembic/         12 migration versions
  tests/           553 unit + 34 integration tests + mutation tests
frontend/
  src/pages/       Dashboard, StockDetail, Sentiment, Signals, Backtest,
                   Alerts, Admin, Settings, Login, Register
  src/components/  Layout, Charts, Signals, StockDetail, Backtests,
                   Sentiment, Articles, Dashboard, Common
  src/api/         Axios API client modules
  src/types/       TypeScript interfaces
nginx/             Reverse proxy config (SSL/TLS)
deploy/            VM configs (.env examples, systemd service files)
scripts/           Backup, restore, seed scripts
docs/              Architecture, deployment, API reference, data sources, phase specs
```

## Scope

Currently tracking **~86 stocks** across 6 S&P 500 sectors:

| Sector | Example Tickers |
|--------|-----------------|
| Energy | XOM, CVX, COP, SLB, EOG, MPC |
| Financials | JPM, BAC, GS, V, MA, BRK-B |
| Technology | NVDA, MSFT, AAPL, ORCL, PANW |
| Communication Services | META, GOOGL, NFLX, DIS, TMUS |
| Consumer Discretionary | AMZN, TSLA, HD, MCD |
| Market ETFs | SPY, QQQ, DIA, IWM, VTI |

## Optional Features (env flags)

| Flag | Default | Description |
|------|---------|-------------|
| `OPTIONS_FLOW_ENABLED` | false | Options chain data + 7th signal component |
| `ML_ENSEMBLE_ENABLED` | false | LightGBM per-sector signal classifier |
| `LLM_EXTRACTION_ENABLED` | false | Gemini Flash earnings context extraction |

## Documentation

- [Architecture](docs/architecture.md) — system diagrams, database schema, signal algorithm
- [Deployment](docs/deployment.md) — Oracle Cloud VM setup guide
- [API Reference](docs/api-reference.md) — all endpoints
- [Data Sources](docs/data-sources.md) — scraping sources and rate limits

## License

Private project. Not for redistribution.
