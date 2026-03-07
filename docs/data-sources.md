# Data Sources

## News & Articles

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| Yahoo Finance News | HTTP scraping (httpx + BeautifulSoup) | 2 req/s (conservative) | News articles | **Done** | General + per-ticker news pages |
| Finviz | HTTP scraping (httpx + BeautifulSoup) | 1 req/s | News aggregator | **Done** | Per-ticker news table scraping |
| Google News | RSS feed (FeedScraper) | 1 req/min (polite) | News articles | **Done** | Stock market + earnings report feeds |
| Reuters RSS | RSS feed parsing (feedparser) | 1 req/min (polite) | News articles | **Done** | business-finance + markets feeds |
| SEC EDGAR | REST API (httpx) | 10 req/s (stated limit) | Filings (8-K, 10-Q, 10-K) | **Done** | Maps form types to event categories |
| MarketWatch | RSS feed (FeedScraper) | 1 req/min (polite) | News articles | **Done** | Top stories + market pulse feeds |
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

All scrapers extend `BaseScraper` (or `FeedScraper` for RSS/Atom sources) which provides:
- `scrape()` → `parse()` → `store()` pipeline
- Deduplication by `source_url` (unique DB constraint)
- Automatic ticker extraction from article titles and body text (4 patterns)
- Industry keyword matching for broad sector/macro news (80+ keywords → 20 sub-industries)
- `article_stocks` join table linking (with tiered confidence scores)
- `scrape_logs` table logging (articles found, new, errors)

**FeedScraper** (extends BaseScraper): shared base class for RSS/Atom feed scrapers, providing feedparser integration, date parsing, and dedup. Used by Google News and MarketWatch.

Orchestration: Celery `group()` fans out all scrapers in parallel, hourly at :00, then chains FinBERT sentiment processing on new articles.

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

## Technical Indicators (computed, not fetched)

Technical indicators are computed on-the-fly from stored OHLCV data — no external data source needed:

| Indicator | Parameters | Used For |
|-----------|-----------|----------|
| SMA | 20-period, 50-period | Price chart overlays, trend score (SMA crossover) |
| EMA | Configurable | MACD calculation building block |
| RSI | 14-period (Wilder's) | Signal scoring (rsi_score component), RSI sub-chart |
| MACD | Fast=12, Slow=26, Signal=9 | Signal scoring (trend_score component), MACD sub-chart |
| Bollinger Bands | 20-period, 2 std dev | Price chart overlays (volatility visualization) |

Computed via `worker/utils/technical_indicators.py` (pure Python, no external dependencies). The `/market-data/{ticker}/indicators` endpoint fetches extra OHLCV rows for warmup so early indicator values are accurate.

## Historical Data Seeding

On first initialization, `scripts/seed_historical_data.py` downloads the full available price history for all active tickers via yfinance (`period="max"`). This gives ~30+ years of daily OHLCV data (~7,500 rows per ticker, ~340K rows total) so the signal algorithm has deep baselines from day one.

- Batches of 20 tickers with 2s delay between batches
- Upserts via `ON CONFLICT DO UPDATE` (idempotent)
- Skips tickers that already have 5,000+ rows
- Can be triggered via `make seed-history` or `POST /api/admin/seed-history`

## Scope

### Active Sectors (~86 tickers across 6 sectors, 20 sub-industries)

| Sector | Industries | Tickers |
|--------|-----------|---------|
| Energy | Oil & Gas Integrated, E&P, Equipment, Refining, Midstream | XOM, CVX, COP, SLB, EOG, MPC, PSX, VLO, OXY, WMB, HAL, DVN, FANG, KMI, BKR, CTRA, OKE, TRGP |
| Financials | Banks, Insurance, Capital Markets, Payments, Diversified | BRK-B, JPM, V, MA, BAC, WFC, GS, MS, SPGI, BLK, AXP, C, SCHW, CB, MMC, PGR, ICE, AON, CME, MCO, USB, TFC, AIG, MET, ALL |
| Technology | Semiconductors, Software, IT Services, Cybersecurity, Consumer Electronics | NVDA, AMD, INTC, MSFT, AAPL, ORCL, CRM, ADBE, INTU, NOW, PLTR, ACN, IBM, CSCO, PANW, QCOM, TXN, AMAT, MU, AVGO |
| Communication Services | Social Media, Streaming & Entertainment, Telecom | META, GOOGL, NFLX, DIS, TMUS, VZ, T, CMCSA |
| Consumer Discretionary | E-Commerce, EV & Auto, Retail, Restaurants | AMZN, TSLA, HD, LOW, TJX, NKE, MCD, SBUX |
| Market ETFs | ETF | SPY, QQQ, DIA, IWM, VTI |

## Deduplication Strategy

Articles are deduplicated by `source_url` (unique constraint). If the same article appears across multiple sources, each instance is stored separately since they may have different text/framing, but the same URL from the same source is only stored once.

## Ticker Extraction

Articles are mapped to stock tickers using a tiered confidence system:

| Method | Confidence | Example |
|--------|-----------|---------|
| `$TICKER` notation | 0.95 | "$XOM rallies on earnings" |
| `(TICKER)` parenthetical | 0.90 | "Exxon Mobil (XOM) reports..." |
| ALL-CAPS word matching | 0.70 | "...shares of XOM rose..." |
| Company name matching | 0.60 | "Exxon Mobil announced..." |
| Industry keyword matching | 0.45 | "OPEC cuts oil production" → Oil & Gas stocks |

Common false positives excluded: A, I, CEO, CFO, CTO, IPO, SEC, FDA, GDP, CPI, ETF, NYSE, USA, API, etc.

### Industry Keyword Matching

When articles don't match specific tickers but contain industry-relevant keywords, they are linked to all stocks in the matched sub-industry at lower confidence (0.45). This enables broad sector/macro news to flow through the sentiment pipeline.

- **80+ keywords** mapped to 20 sub-industries
- **Cross-cutting themes**: tariffs, sanctions, interest rates, supply chain, etc. map to multiple industries simultaneously
- Keywords are matched longest-first to avoid false positives (e.g., "crude oil" matched before "oil")
- Example: *"US could lift sanctions on more Russian oil"* → matches "sanctions" + "oil" → links to XOM, CVX, COP, OXY
