# Data Sources

## News & Articles

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| Yahoo Finance News | HTTP scraping (httpx + BeautifulSoup) | 2 req/s (conservative) | News articles | **Done** | General + per-ticker news pages |
| Finviz | HTTP scraping (httpx + BeautifulSoup) | 1 req/s | News aggregator | **Done** | Per-ticker news table scraping |
| Google News | RSS feed (FeedScraper) | 1 req/min (polite) | News articles | **Done** | Stock market + earnings report feeds; 7th live source (replaced Reuters scraper) |
| SEC EDGAR | REST API (httpx) | 10 req/s (stated limit) | Filings (8-K, 10-Q, 10-K) | **Done** | Maps form types to event categories |
| MarketWatch | RSS feed (FeedScraper) | 1 req/min (polite) | News articles | **Done** | Top stories + market pulse feeds |
| Reddit (r/stocks, r/wallstreetbets) | PRAW (Reddit API) | 60 req/min | Posts | **Done** | Filters by score >= 10, skips stickied; credibility 0.4; retail_sentiment_score only |
| FRED (Federal Reserve Economic Data) | RSS feed (FeedScraper) | polite | Economic indicator releases, macro context | **Done** | CPI, unemployment, Fed rate, GDP, T10Y2Y, VIX release articles |

## Market Data

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| yfinance | Python library | No official limit, be conservative | OHLCV daily + intraday | **Done** | Free, no API key. Hourly 5d fetch + full historical seed (max ~30+ years) |
| Polygon.io | REST API (free tier) | 5 API calls/min | OHLCV end-of-day | Planned | Backup source, 25 req/day on free tier |

## Options Data

| Source | Method | Rate Limit | Data Type | Status | Notes |
|--------|--------|------------|-----------|--------|-------|
| yfinance options chain | `Ticker.options` + `Ticker.option_chain` | Conservative | P/C ratio, IV skew, volume/OI aggregates | **Done** | Nearest 3 expirations; weekdays at :10 UTC |
| CBOE put/call ratio | CBOE public website | polite | Market-wide P/C ratio | **Done** | Weekdays at :12 UTC |

**Options data details:**
- Nearest 3 expirations per ticker aggregated into daily snapshots
- Per-ticker data quality tracked: `full` (all expirations loaded), `partial` (some failed), `stale` (last fetch was prior trading day)
- Aggregates: weighted average IV, ATM strike IV, put volume, call volume, put OI, call OI, P/C ratio, IV skew
- Gated signal component (`options_score`): enabled via `OPTIONS_FLOW_ENABLED=true`
- Scoring: `0.6 * -tanh(pcr_z) + 0.4 * -tanh(skew_z)` where z-scores are computed vs a 20-day rolling baseline

## Insider Transactions (Form 4)

| Source | Method | Data Type | Status | Notes |
|--------|--------|-----------|--------|-------|
| yfinance `Ticker.insider_transactions` | Python library | SEC Form 4 filings | **Done** | Daily 18:00 UTC fetch (after US market close + filing deadline) |

**Insider data details:**
- Data: insider name, title, transaction type (Purchase/Sale/Award/Disposal), shares, price, value
- Stored in `insider_transactions` table; soft-deduplicated by (ticker, insider name, date, shares)
- 30-day rolling window for `insider_score` computation
- Role weighting: CEO/CFO/Chairman get higher weight than directors/VPs
- Sell discount: sale transactions counted at 40% of their notional value
- Scoring: `tanh(net_value / 500_000)` — net buying → positive, net selling → negative
- Gated signal component (8% weight): enabled via `INSIDER_FLOW_ENABLED=true`

## LLM Extraction Pipeline

| Model | Method | Data Type | Status | Notes |
|-------|--------|-----------|--------|-------|
| Claude Haiku (`claude-haiku-4-5-20251001`) | Anthropic SDK | Structured fields from article text | **Done** | Every 2h at :20; quality gate ≥ 0.60; 50 articles/run cap |

**What is extracted:**

*Earnings articles (event_category = 'earnings'):*
- `guidance_change`: `positive` / `negative` / `none` — stored on `EarningsEstimate`; modifies `earnings_score` by ±0.20
- `management_tone`: float −1.0 to 1.0 — modifies `earnings_score` by ±0.10

*Analyst rating articles (event_category = 'analyst_rating'):*
- `rating_change`: `upgrade` / `downgrade` / `initiate` / `reiterate`
- `price_target`: float (USD)
- `analyst_firm`: string
- Stored in `article.metadata_` JSONB; feed the gated `analyst_score` component (0.07 weight)

**Gates:**
- `LLM_EXTRACTION_ENABLED=true` — must be set on both Docker VM and Compute VM
- `ANTHROPIC_API_KEY` — required
- `quality_score ≥ 0.60` — articles below this threshold are skipped
- Cap of 50 articles per run (shared across earnings + analyst categories)
- `llm_extracted` column tracks status: `NULL` (not attempted), `True` (succeeded), `False` (failed/skipped)

## Scraper Architecture

All scrapers extend `BaseScraper` (or `FeedScraper` for RSS/Atom sources) which provides:
- `scrape()` → `parse()` → `store()` pipeline
- Deduplication by `source_url` (unique DB constraint)
- Automatic ticker extraction from article titles and body text (4 patterns)
- Industry keyword matching for broad sector/macro news (80+ keywords → 20 sub-industries)
- `article_stocks` join table linking (with tiered confidence scores)
- `scrape_logs` table logging (articles found, new, errors)
- Event classification (10 categories) and fuzzy duplicate detection on every stored article

**FeedScraper** (extends BaseScraper): shared base class for RSS/Atom feed scrapers, providing
feedparser integration, date parsing, and dedup. Used by Google News, MarketWatch, and FRED.

Orchestration: Celery `group()` fans out all scrapers in parallel, hourly at :00, then chains
FinBERT sentiment processing on new articles.

## Article Processing Pipeline

After scraping, each article passes through several quality and deduplication layers before
it can contribute to signal scoring:

### 1. Fuzzy Duplicate Detection

Rapidfuzz `token_set_ratio` compares new article titles against all titles from the same
ticker within a 24-hour window. Articles scoring above the similarity threshold are marked
as duplicates of the earliest-seen article (`canonical_article_id`). Duplicate groups are
tracked via `duplicate_group_id`. Non-canonical articles are excluded from signal scoring
but remain stored for reference.

### 2. Article Quality Scoring

Every article receives a `quality_score` (0–1) computed from four weighted components:

| Component | Weight | Description |
|-----------|--------|-------------|
| Source credibility | 40% | Per-source credibility score (see table below) |
| Quantitative content | 25% | Presence of numbers, percentages, financial figures |
| Ticker confidence | 25% | Highest confidence score of any ticker association |
| Article length | 10% | Normalised word count (longer = higher, up to a ceiling) |

**Quality gates:**
- `quality_score < 0.40`: article excluded from signal scoring entirely
- `quality_score < 0.60`: article excluded from LLM extraction

### 3. Source Credibility Weights

| Source | Credibility |
|--------|-------------|
| SEC EDGAR | 1.0 |
| Reuters (`reuters` / `reuters_rss`) | 0.9 |
| MarketWatch | 0.8 |
| Yahoo Finance | 0.7 |
| FRED | 0.7 |
| Finviz | 0.6 |
| Google News | 0.6 |
| Reddit | 0.4 |

Note: Reuters credibility aliases (`reuters` and `reuters_rss`) are preserved for historical
rows. The Reuters RSS scraper was removed; Google News is the current 7th live source.

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
- Reddit articles are processed into a separate `retail_sentiment_score` on signals (not mixed into the main sentiment components)

## Technical Indicators (computed, not fetched)

Technical indicators are computed on-the-fly from stored OHLCV data — no external data source needed:

| Indicator | Parameters | Used For |
|-----------|-----------|----------|
| SMA | 20-period, 50-period | Price chart overlays, trend score (SMA crossover) |
| EMA | Configurable | MACD calculation building block |
| RSI | 14-period (Wilder's) | Regime multiplier (±15% on composite); RSI sub-chart |
| MACD | Fast=12, Slow=26, Signal=9 | Regime multiplier (trend score component); MACD sub-chart |
| Bollinger Bands | 20-period, 2 std dev | Price chart overlays (volatility visualization) |

RSI and MACD/trend are **not** additive signal components. They feed `apply_regime_multiplier()`
in `signal_formula.py`, which boosts or dampens the composite score by ±15% and labels the
signal with a `market_regime` (trending_up / trending_down / overbought / oversold / sideways).

Computed via `worker/utils/technical_indicators.py` (pure Python, no external dependencies).
The `/market-data/{ticker}/indicators` endpoint fetches extra OHLCV rows for warmup so early
indicator values are accurate.

## Historical Data Seeding

On first initialization, `scripts/seed_historical_data.py` downloads the full available price
history for all active tickers via yfinance (`period="max"`). This gives ~30+ years of daily
OHLCV data (~7,500 rows per ticker) so the signal algorithm has deep baselines from day one.

- Batches of 20 tickers with 2s delay between batches
- Upserts via `ON CONFLICT DO UPDATE` (idempotent)
- Skips tickers that already have 5,000+ rows
- Can be triggered via `make seed-history` or `POST /api/admin/seed-history`

## Scope

### Active Sectors (~91 tickers across 6 sectors, including sector benchmark ETFs)

| Sector | Industries | Notable Tickers |
|--------|-----------|---------|
| Energy | Oil & Gas Integrated, E&P, Equipment, Refining, Midstream | XOM, CVX, COP, SLB, EOG, MPC, PSX, VLO, OXY, WMB, HAL, DVN, FANG, KMI, BKR, CTRA, OKE, TRGP |
| Financials | Banks, Insurance, Capital Markets, Payments, Diversified | BRK-B, JPM, V, MA, BAC, WFC, GS, MS, SPGI, BLK, AXP, C, SCHW, CB, MMC, PGR, ICE, AON, CME, MCO, USB, TFC, AIG, MET, ALL |
| Technology | Semiconductors, Software, IT Services, Cybersecurity, Consumer Electronics | NVDA, AMD, INTC, MSFT, AAPL, ORCL, CRM, ADBE, INTU, NOW, PLTR, ACN, IBM, CSCO, PANW, QCOM, TXN, AMAT, MU, AVGO |
| Communication Services | Social Media, Streaming & Entertainment, Telecom | META, GOOGL, NFLX, DIS, TMUS, VZ, T, CMCSA |
| Consumer Discretionary | E-Commerce, EV & Auto, Retail, Restaurants | AMZN, TSLA, HD, LOW, TJX, NKE, MCD, SBUX |
| Market ETFs | ETF | SPY, QQQ, DIA, IWM, VTI, XLE, XLF, XLK, XLC, XLY |

**Sector benchmark ETFs** (XLE, XLF, XLK, XLC, XLY) are included in Market ETFs and serve a
dual purpose: they are traded as signals like any other ticker, and they are used as sector
return benchmarks when computing `is_correct` for daily-view outcomes (excess return vs the
sector ETF). Market ETFs themselves use absolute return for `is_correct`.

## Deduplication Strategy

Articles are deduplicated by `source_url` (unique constraint). If the same article appears
across multiple sources, each instance is stored separately since they may have different
text/framing, but the same URL from the same source is only stored once.

In addition, fuzzy title matching (rapidfuzz token_set_ratio) runs within 24-hour windows
per ticker to detect cross-source duplicates. Non-canonical articles are excluded from
signal scoring but not deleted.

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

A per-article `ticker_confidence` score (highest confidence across all extracted tickers) feeds
into the article quality score (25% weight). Articles from Reddit are flagged and their sentiment
is isolated into a separate `retail_sentiment_score` component rather than mixed into the main
sentiment momentum and sentiment volume components.

### Industry Keyword Matching

When articles don't match specific tickers but contain industry-relevant keywords, they are
linked to all stocks in the matched sub-industry at lower confidence (0.45). This enables
broad sector/macro news to flow through the sentiment pipeline.

- **80+ keywords** mapped to 20 sub-industries
- **Cross-cutting themes**: tariffs, sanctions, interest rates, supply chain, etc. map to multiple industries simultaneously
- Keywords are matched longest-first to avoid false positives (e.g., "crude oil" matched before "oil")
- Example: *"US could lift sanctions on more Russian oil"* → matches "sanctions" + "oil" → links to XOM, CVX, COP, OXY
