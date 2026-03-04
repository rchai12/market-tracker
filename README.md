# Stock Predictor

A sentiment-driven stock market prediction system that scrapes financial news, runs FinBERT sentiment analysis, correlates with market data, and generates composite trading signals with Discord/email alerts.

## Features

- **News Scraping**: Hourly ingestion from 7 sources (Yahoo Finance, Finviz, Reuters, SEC EDGAR, MarketWatch, Reddit, FRED)
- **Historical Data**: Full available price history (~30+ years) seeded on initialization via yfinance
- **Sentiment Analysis**: FinBERT model scores every article as bullish/bearish/neutral
- **Signal Generation**: Composite scoring algorithm combining sentiment momentum, article volume, price momentum, and volume anomalies
- **Real-time Alerts**: Discord webhook and email notifications when signals trigger
- **Web Dashboard**: React app with TradingView charts, sentiment timelines, signal feeds, and watchlists
- **JWT Authentication**: Secure user accounts with watchlists and alert preferences

## Architecture

Runs on two Oracle Cloud free-tier ARM VMs:

| VM | Role | Services |
|----|------|----------|
| Docker VM | Application hosting | Postgres 16, Redis 7, FastAPI, React, Nginx |
| Compute VM | Data processing | Celery workers (2 cores), FinBERT model (12GB RAM) |

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Node.js 20+

### Setup

```bash
# Clone the repo
git clone <repo-url> stock-predictor
cd stock-predictor

# Create environment file
cp .env.example .env
# Edit .env with your actual values (database passwords, API keys, etc.)

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
# Backend (FastAPI with hot reload)
make dev-backend

# Frontend (Vite dev server)
make dev-frontend

# Run tests
make test

# Lint
make lint
```

## Tech Stack

### Backend
- **FastAPI** — async Python web framework
- **SQLAlchemy 2.0** — async ORM with PostgreSQL
- **Celery + Redis** — distributed task queue
- **FinBERT** — financial sentiment analysis model
- **yfinance** — market data (OHLCV, full history)
- **Alembic** — database migrations

### Frontend
- **React 19** + TypeScript
- **Vite** — build tooling
- **TanStack Query** — server state management
- **Zustand** — client state
- **TradingView Lightweight Charts** — financial charting
- **Tailwind CSS** — styling

### Infrastructure
- **PostgreSQL 16** — primary database
- **Redis 7** — Celery broker + rate limiter backend
- **Nginx** — reverse proxy with rate limiting
- **Docker Compose** — container orchestration

## Project Structure

```
backend/           FastAPI + Celery + SQLAlchemy
  app/api/         Route handlers (auth, stocks, watchlist, market_data, articles, sentiment, signals, alerts, admin)
  app/models/      SQLAlchemy ORM models (13 tables)
  app/schemas/     Pydantic schemas
  worker/tasks/    Celery tasks (scraping, sentiment, signals)
    scraping/      7 scrapers + orchestrator + market data
    sentiment/     FinBERT analyzer (singleton) + sentiment processing task
    signals/       Signal generator (composite scoring) + alert dispatcher (Discord + email)
  worker/utils/    Rate limiter, text cleaner, ticker extractor
frontend/          React + TypeScript
  src/pages/       Route pages (Dashboard, StockDetail, Sentiment, Signals, Alerts, etc.)
  src/components/  UI components (layout, charts, sentiment, signals, dashboard, common)
  src/api/         API client modules
nginx/             Reverse proxy config
scripts/           Setup and seed scripts (tickers + historical data)
deploy/            VM deployment configs
docs/              Architecture, deployment, API reference, data sources
```

## Scope

Currently tracking **45 stocks** across two S&P 500 sectors:
- **Energy**: XOM, CVX, COP, SLB, EOG, MPC, and more
- **Financials**: JPM, BAC, GS, V, MA, BRK-B, and more

Additional sectors can be activated in the database.

## Documentation

- [Architecture](docs/architecture.md) — system diagrams, database schema, signal algorithm
- [Deployment](docs/deployment.md) — Oracle Cloud VM setup guide
- [API Reference](docs/api-reference.md) — all endpoints
- [Data Sources](docs/data-sources.md) — scraping sources and rate limits

## License

Private project. Not for redistribution.
