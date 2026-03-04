# Data Sources

## News & Articles

| Source | Method | Rate Limit | Data Type | Notes |
|--------|--------|------------|-----------|-------|
| Yahoo Finance News | HTTP scraping | 2 req/s (conservative) | News articles | Broad coverage, easy to scrape |
| Finviz | HTTP scraping | 1 req/s | News aggregator | Good for per-ticker news |
| Reuters RSS | RSS feed parsing | 1 req/min (polite) | News articles | High quality journalism |
| SEC EDGAR | REST API | 10 req/s (stated limit) | Filings (8-K, 10-Q, 10-K), Form 4 | Official filings, high signal |
| MarketWatch | HTTP scraping | 1 req/s | News articles | Market commentary |
| Reddit (r/stocks, r/wallstreetbets) | PRAW (Reddit API) | 60 req/min | Posts + comments | Retail sentiment signal |

## Market Data

| Source | Method | Rate Limit | Data Type | Notes |
|--------|--------|------------|-----------|-------|
| yfinance | Python library | No official limit, be conservative | OHLCV daily + intraday | Free, no API key, primary source |
| Polygon.io | REST API (free tier) | 5 API calls/min | OHLCV end-of-day | Backup source, 25 req/day on free tier |

## Economic Indicators

| Source | Method | Rate Limit | Data Type | Notes |
|--------|--------|------------|-----------|-------|
| FRED (Federal Reserve) | REST API | 120 req/min | CPI, jobs, PMI, Fed rate | Free API key required |

## Scope

### Phase 1 Sectors
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
