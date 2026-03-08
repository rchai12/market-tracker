# Stock Predictor

A sentiment-driven stock market prediction system that scrapes financial news, runs FinBERT sentiment analysis, correlates with market data, and generates composite trading signals with Discord/email alerts.

## Features

- **News Scraping**: Hourly ingestion from 7 sources (Yahoo Finance, Finviz, Google News, Reuters RSS, SEC EDGAR, MarketWatch, Reddit, FRED)
- **Historical Data**: Full available price history (~30+ years) seeded on initialization via yfinance
- **Ticker & Industry Linking**: 4-tier ticker extraction ($TICKER, parenthetical, ALL-CAPS, company name) plus industry keyword matching for sector-level news (80+ keywords, cross-cutting macro themes)
- **Sentiment Analysis**: FinBERT model scores every article as bullish/bearish/neutral
- **Signal Generation**: 6-component composite scoring (sentiment momentum, article volume, price momentum, volume anomaly, RSI, trend) with adaptive per-sector weights
- **Technical Indicators**: RSI (14), SMA (20/50), EMA, MACD (12/26/9), Bollinger Bands — computed on-the-fly from stored OHLCV data
- **Backtesting Engine**: Replay signal generation over historical data with equity curves, trade logs, and performance metrics (Sharpe, drawdown, win rate). Technical mode (OHLCV only, full history) and full mode (+ sentiment)
- **News Intelligence**: Rule-based event classification (10 categories), fuzzy duplicate detection across sources (rapidfuzz), source credibility weighting in signal scoring (SEC > Reuters > Reddit)
- **Signal Intelligence**: Expandable signal cards with 6-component breakdown bars, signal detail panel with outcomes + linked articles, accuracy trend/distribution charts, methodology tab with adaptive weights table
- **Signal Feedback Loop**: Outcome evaluation (1/3/5-day windows), adaptive weight optimization, accuracy tracking
- **Real-time Alerts**: Discord webhook and email notifications when signals trigger
- **Web Dashboard**: React app with TradingView charts, indicator overlays (SMA, Bollinger), RSI/MACD sub-charts, sentiment timelines, signal feeds, accuracy metrics, and watchlists
- **Stock Search**: Type-ahead search bar in header with debounced dropdown for quick stock navigation
- **Admin Dashboard**: Frontend UI for admin tasks (scrape triggers, maintenance, DB stats) — no CLI required
- **Mobile Responsive**: Collapsible sidebar drawer on small screens with hamburger toggle
- **Code Splitting**: Lazy-loaded route pages via React.lazy + Suspense for faster initial load
- **Data Maintenance**: Automated retention (article compression, log cleanup, weak signal purge), materialized views
- **JWT Authentication**: Secure user accounts with profile editing, password management, watchlists, and alert preferences

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
  app/api/         Route handlers (auth, stocks, watchlist, market_data, articles, sentiment, signals, alerts, backtests, admin)
  app/models/      SQLAlchemy ORM models (15 tables)
  app/schemas/     Pydantic schemas
  worker/tasks/    Celery tasks (scraping, sentiment, signals, maintenance)
    scraping/      7 scrapers + FeedScraper base + orchestrator + market data
    sentiment/     FinBERT analyzer (singleton) + sentiment processing task
    signals/       Signal generator + component scores + alert dispatcher + outcome evaluator + weight optimizer + backtest task
    maintenance/   Data retention (compression, cleanup, purge) + matview refresh
  worker/utils/    Rate limiter, text cleaner, ticker extractor, celery_helpers, technical indicators, backtester/
frontend/          React + TypeScript
  src/pages/       Route pages (Dashboard, StockDetail, Sentiment, Signals, Backtest, Alerts, Admin, Settings)
  src/components/  UI components (layout + search, charts, sentiment, signals, stock-detail, backtests, dashboard, common)
  src/api/         API client modules (auth, stocks, signals, sentiment, alerts, backtests, admin)
nginx/             Reverse proxy config
scripts/           Setup and seed scripts (tickers + historical data)
deploy/            VM deployment configs
docs/              Architecture, deployment, API reference, data sources
```

## Scope

Currently tracking **~86 stocks** across 6 S&P 500 sectors with 20 sub-industry classifications:

| Sector | Industries | Example Tickers |
|--------|-----------|-----------------|
| Energy | Oil & Gas Integrated, E&P, Equipment, Refining, Midstream | XOM, CVX, COP, SLB, EOG, MPC |
| Financials | Banks, Insurance, Capital Markets, Payments | JPM, BAC, GS, V, MA, BRK-B |
| Technology | Semiconductors, Software, IT Services, Cybersecurity, Consumer Electronics | NVDA, MSFT, AAPL, ORCL, PANW |
| Communication Services | Social Media, Streaming & Entertainment, Telecom | META, GOOGL, NFLX, DIS, TMUS |
| Consumer Discretionary | E-Commerce, EV & Auto, Retail, Restaurants | AMZN, TSLA, HD, MCD |
| Market ETFs | ETF | SPY, QQQ, DIA, IWM, VTI |

Industry classifications enable keyword-based article linking — broad news like "OPEC cuts production" automatically links to Oil & Gas stocks even without explicit ticker mentions.

## Documentation

- [Architecture](docs/architecture.md) — system diagrams, database schema, signal algorithm
- [Deployment](docs/deployment.md) — Oracle Cloud VM setup guide
- [API Reference](docs/api-reference.md) — all endpoints
- [Data Sources](docs/data-sources.md) — scraping sources and rate limits

## License

Private project. Not for redistribution.
