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
│  │  - scraping            │  │  - :00 scrape all      │   │
│  │  - sentiment           │  │  - :05 market data     │   │
│  │  - signals             │  │  - :30 gen signals     │   │
│  │  - default             │  │  - 3AM maintenance     │   │
│  └──────────────────────┘  └────────────────────────┘   │
│                                                          │
│  ┌──────────────────────┐                               │
│  │   FinBERT Model      │                               │
│  │   (~1.5GB in memory) │                               │
│  └──────────────────────┘                               │
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
                   │   Signal    │
                   │  Generator  │
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
       │  React App  │
       │ (Dashboard, │
       │  Charts,    │
       │  Signals)   │
       └─────────────┘
```

## Database Schema

### Entity Relationships

```
users ──< watchlist_items >── stocks
users ──< alert_configs
stocks ──< article_stocks >── articles
stocks ──< market_data_daily
stocks ──< market_data_intraday
articles ──< sentiment_scores
stocks ──< signals
signals ──< alert_logs
stocks >── sectors
```

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| users | Authentication and preferences | email, username, password_hash, discord_webhook_url |
| sectors | Stock groupings (Energy, Financials, ...) | name, is_active |
| stocks | S&P 500 tickers | ticker, company_name, sector_id, is_active |
| market_data_daily | Historical OHLCV | stock_id, date, open/high/low/close/volume |
| market_data_intraday | Intraday prices | stock_id, timestamp, OHLCV |
| articles | Scraped news/filings | source, source_url, title, raw_text, is_processed |
| article_stocks | Article-to-ticker mapping | article_id, stock_id, confidence |
| sentiment_scores | FinBERT analysis results | article_id, label, positive/negative/neutral scores |
| signals | Composite trading signals | stock_id, direction, strength, composite_score, reasoning |
| alert_configs | User alert preferences | user_id, stock_id, min_strength, channel |
| alert_logs | Sent alert history | signal_id, user_id, channel, success |
| watchlist_items | User watchlists | user_id, stock_id |
| scrape_logs | Scraper execution logs | source, articles_found, articles_new, errors |

## Signal Scoring Algorithm

The composite signal combines four components:

```
composite = 0.40 * sentiment_momentum
          + 0.25 * sentiment_volume
          + 0.20 * price_momentum
          + 0.15 * volume_anomaly
```

| Component | Description | Range |
|-----------|-------------|-------|
| sentiment_momentum | Exponentially weighted avg of sentiment scores (half-life 6h) | [-1, 1] |
| sentiment_volume | Article count vs 20-day baseline, amplifies direction | [0, 1] |
| price_momentum | 5-day price change, tanh scaled | [-1, 1] |
| volume_anomaly | Trading volume vs 20-day avg, amplifies direction | [0, 1] |

**Thresholds:**
- Strong: |composite| > 0.6
- Moderate: |composite| > 0.35
- Weak: everything else

## Historical Data Initialization

On first setup, `scripts/seed_historical_data.py` backfills the full available price history for all active tickers via yfinance (`period="max"`). This provides ~30+ years of daily OHLCV data per ticker (~7,500 rows each, ~340K total rows, ~50MB in Postgres).

This ensures the signal algorithm has deep historical baselines (20-day moving averages for price momentum and volume anomaly) from day one, rather than starting blind and needing weeks to accumulate enough data.

The historical seed is idempotent (upserts via `ON CONFLICT DO UPDATE`) and skips tickers that already have 5,000+ rows.

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
