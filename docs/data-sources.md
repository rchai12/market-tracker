# Data Sources

## News & Articles

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| Yahoo Finance News | HTTP scraping (httpx + BeautifulSoup) | 2 req/s (conservative) | News articles | **Done** | General + per-ticker news pages |
| Finviz | HTTP scraping (httpx + BeautifulSoup) | 1 req/s | News aggregator | **Done** | Per-ticker news table scraping |
| Reuters RSS | RSS feed parsing (feedparser) | 1 req/min (polite) | News articles | **Done** | business-finance + markets feeds |
| SEC EDGAR | REST API (httpx) | 10 req/s (stated limit) | Filings (8-K, 10-Q, 10-K) | **Done** | Maps form types to event categories |
| MarketWatch | HTTP scraping (httpx + BeautifulSoup) | 1 req/s | News articles | **Done** | Latest news page scraping |
| Reddit (r/stocks, r/wallstreetbets) | PRAW (Reddit API) | 60 req/min | Posts | **Done** | Filters by score >= 10, skips stickied |

## Market Data

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| yfinance | Python library | No official limit, be conservative | OHLCV daily + intraday | **Done** | Free, no API key. Hourly 5d fetch + full historical seed (max ~30+ years) |
| Polygon.io | REST API (free tier) | 5 API calls/min | OHLCV end-of-day | Planned | Backup source, 25 req/day on free tier |

## Economic Indicators

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| FRED (Federal Reserve) | REST API (httpx) | 120 req/min | CPI, unemployment, Fed rate, GDP, T10Y2Y, VIX | **Done** | Fetches releases/dates API |

## Scraper Architecture

All scrapers extend `BaseScraper` which provides:
- `scrape()` → `parse()` → `store()` pipeline
- Deduplication by `source_url` (unique DB constraint)
- Automatic ticker extraction from article titles and body text
- `article_stocks` join table linking (with confidence scores)
- `scrape_logs` table logging (articles found, new, errors)

Orchestration: Celery `group()` fans out all 7 scrapers in parallel, hourly at :00, then chains FinBERT sentiment processing on new articles.

## Sentiment Analysis (FinBERT)

| Model | Method | Status | Notes |
|-------|--------|--------|-------|
| ProsusAI/finbert | PyTorch inference (CPU) | **Done** | Singleton model, lazy-loaded on first use, ~1.5GB in memory |

**Processing pipeline:**
- Automatically triggered after scraper orchestration completes (chained task)
- Catch-up task runs at :15 every hour as a safety net
- Analyzes article text: prefers `raw_text` → `summary` → `title`
- Long texts (>2048 chars) are chunked at sentence boundaries, scores averaged
- Batch inference with configurable batch size (default 16) and max token length (default 512)
- Stores per-article-per-stock sentiment scores (positive/negative/neutral probabilities + dominant label)

## Historical Data Seeding

On first initialization, `scripts/seed_historical_data.py` downloads the full available price history for all active tickers via yfinance (`period="max"`). This gives ~30+ years of daily OHLCV data (~7,500 rows per ticker, ~340K rows total) so the signal algorithm has deep baselines from day one.

- Batches of 20 tickers with 2s delay between batches
- Upserts via `ON CONFLICT DO UPDATE` (idempotent)
- Skips tickers that already have 5,000+ rows
- Can be triggered via `make seed-history` or `POST /api/admin/seed-history`

## Scope

### Active Sectors
- **Energy**: XOM, CVX, COP, SLB, EOG, MPC, PXD, PSX, VLO, OXY, WMB, HES, HAL, DVN, FANG, KMI, BKR, CTRA, OKE, TRGP
- **Financials**: BRK-B, JPM, V, MA, BAC, WFC, GS, MS, SPGI, BLK, AXP, C, SCHW, CB, MMC, PGR, ICE, AON, CME, MCO, USB, TFC, AIG, MET, ALL

### Future Expansion
Remaining S&P 500 sectors (stored as inactive in the sectors table):
Technology, Health Care, Consumer Discretionary, Communication Services, Industrials, Consumer Staples, Utilities, Real Estate, Materials

## Deduplication Strategy

Articles are deduplicated by `source_url` (unique constraint). If the same article appears across multiple sources, each instance is stored separately since they may have different text/framing, but the same URL from the same source is only stored once.

## Ticker Extraction

Articles are mapped to stock tickers using:
1. `$TICKER` notation in text (confidence 0.95)
2. ALL CAPS words matching known tickers (confidence 0.70)
3. Common false positives excluded: A, I, CEO, CFO, CTO, IPO, SEC, FDA, GDP, CPI, ETF, NYSE, USA, API
