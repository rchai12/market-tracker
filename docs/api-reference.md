# API Reference

Base URL: `/api`

All protected endpoints accept **either** a JWT Bearer token **or** an API key in the Authorization header:

```
Authorization: Bearer <jwt_token>
Authorization: Bearer sp_<32hexchars>
```

API keys are generated via `POST /auth/api-keys` and stored SHA-256 hashed. The raw key is shown only once on creation.

Status legend: **Done** = implemented.

---

## Response Envelope

Paginated list endpoints return:
```json
{
  "data": [ ... ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

Single-item endpoints return the object directly. All `per_page` values are capped at 100.

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Basic liveness check; `?detail=true` also checks DB and Redis connectivity |

```json
// GET /health?detail=true
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "version": "1.0.0"
}
```

---

## Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Create new account (201) |
| POST | `/auth/login` | No | Login — OAuth2 form; `username` field accepts email |
| POST | `/auth/refresh` | No | Exchange refresh token for a new access token |
| GET | `/auth/me` | Yes | Get current user profile |
| PUT | `/auth/profile` | Yes | Update username and/or email |
| PUT | `/auth/password` | Yes | Change password |
| POST | `/auth/api-keys` | Yes | Create API key (max 5 per user; 201) |
| GET | `/auth/api-keys` | Yes | List user's API keys |
| DELETE | `/auth/api-keys/{id}` | Yes | Soft-revoke API key (204) |

### POST /auth/register
```json
// Request
{ "email": "user@example.com", "username": "alice", "password": "Secret123" }

// Response (201)
{
  "user": { "id": 1, "email": "user@example.com", "username": "alice", "is_active": true, "is_admin": false },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

Validation:
- Username: 3–50 characters, unique
- Password: min 8 chars, at least one uppercase, one lowercase, one digit
- Email: valid format, unique

### POST /auth/login
```
// Request (application/x-www-form-urlencoded)
username=user@example.com&password=Secret123

// Response — same shape as /register
```

`/auth/login` is rate-limited to 5 requests per minute per IP (nginx).

### POST /auth/refresh
```json
// Request
{ "refresh_token": "eyJ..." }

// Response — same shape as /login
```

### GET /auth/me
```json
// Response
{ "id": 1, "email": "user@example.com", "username": "alice", "is_active": true, "is_admin": false }
```

### PUT /auth/profile
```json
// Request (all fields optional, at least one required)
{ "username": "alice2", "email": "new@example.com" }

// Response
{ "id": 1, "email": "new@example.com", "username": "alice2", "is_active": true, "is_admin": false }
```

### PUT /auth/password
```json
// Request
{ "current_password": "Secret123", "new_password": "NewSecret456" }

// Response
{ "message": "Password updated" }
```

### POST /auth/api-keys
```json
// Request
{ "name": "My Script", "expires_in_days": 90 }

// Response (201) — raw key shown ONCE; store it securely
{
  "id": 1,
  "name": "My Script",
  "key": "sp_4a7b9c...",
  "key_prefix": "sp_4a7b9c",
  "created_at": "2025-06-15T10:00:00Z"
}
```

`expires_in_days` is optional. When omitted the key does not expire.

### GET /auth/api-keys
```json
// Response
[
  {
    "id": 1,
    "name": "My Script",
    "key_prefix": "sp_4a7b9c",
    "is_active": true,
    "created_at": "2025-06-15T10:00:00Z",
    "last_used_at": "2025-06-20T08:00:00Z",
    "expires_at": "2025-09-15T10:00:00Z"
  }
]
```

### DELETE /auth/api-keys/{id}
Sets `is_active = false`. Returns 204.

---

## Stocks

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/stocks` | Yes | Paginated stock list, filterable by sector and search |
| GET | `/stocks/sectors` | Yes | Dynamic list of active sector names from DB |
| GET | `/stocks/{ticker}` | Yes | Stock detail: ticker, company name, sector, industry |

### GET /stocks
Query params: `?sector=Technology&search=apple&page=1&per_page=20`

```json
{
  "data": [
    { "id": 5, "ticker": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics", "is_active": true }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 91, "total_pages": 5 }
}
```

### GET /stocks/sectors
```json
["Communication Services", "Consumer Discretionary", "Energy", "Financials", "Market ETFs", "Technology"]
```

---

## Market Data

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/market-data/{ticker}/daily` | Yes | Daily OHLCV |
| GET | `/market-data/{ticker}/intraday` | Yes | Intraday OHLCV |
| GET | `/market-data/{ticker}/indicators` | Yes | Technical indicators computed on-the-fly |
| GET | `/market-data/{ticker}/options` | Yes | Options chain snapshot with put/call ratio and IV skew |
| GET | `/market-data/{ticker}/insider-activity` | Yes | Form 4 insider transactions (90-day window) + current insider_score |
| GET | `/market-data/cboe/put-call-ratio` | Yes | Market-wide CBOE put/call ratio history |

### GET /market-data/{ticker}/daily
Query params: `?start_date=2025-01-01&end_date=2025-12-31&limit=365`

```json
[
  { "date": "2025-06-15", "open": 192.1, "high": 195.3, "low": 191.5, "close": 194.8, "volume": 58200000 }
]
```

### GET /market-data/{ticker}/indicators
Computes RSI (14-period Wilder's), SMA (20/50), MACD (12/26/9), and Bollinger Bands on-the-fly from stored OHLCV. Extra warmup rows are fetched internally so early values are not cold-start biased.

Query params: `?days=365` (default 365)

```json
[
  {
    "date": "2025-06-15",
    "sma20": 145.32,
    "sma50": 142.18,
    "rsi": 62.5,
    "macd_line": 1.23,
    "macd_signal": 0.98,
    "macd_histogram": 0.25,
    "bb_upper": 152.10,
    "bb_middle": 145.32,
    "bb_lower": 138.54
  }
]
```

### GET /market-data/{ticker}/options
Returns the most recent options chain snapshot for the ticker. Data is sourced from yfinance and stored daily at :10 (weekdays). Includes per-ticker data quality (`full` / `partial` / `stale`).

```json
{
  "ticker": "XOM",
  "snapshot_date": "2025-06-15",
  "data_quality": "full",
  "put_call_ratio": 0.82,
  "iv_skew": 0.05,
  "weighted_avg_iv": 0.31,
  "atm_iv": 0.29,
  "total_call_volume": 42300,
  "total_put_volume": 34600,
  "total_call_oi": 210000,
  "total_put_oi": 172000,
  "history": [
    {
      "date": "2025-06-14",
      "put_call_ratio": 0.79,
      "iv_skew": 0.04,
      "weighted_avg_iv": 0.30
    }
  ]
}
```

`history` contains the 20-day baseline used for z-score anomaly detection in the options signal component.

### GET /market-data/{ticker}/insider-activity
Returns up to 90 days of Form 4 insider transactions sourced from yfinance, plus the current gated `insider_score` for the ticker (null when the gate is inactive or no data within 30 days).

```json
{
  "ticker": "XOM",
  "insider_score": 0.41,
  "transactions": [
    {
      "id": 10,
      "insider_name": "John Doe",
      "insider_title": "Director",
      "transaction_type": "purchase",
      "shares": 5000,
      "value": 450000.0,
      "transaction_date": "2025-06-10",
      "scraped_at": "2025-06-11T18:05:00Z"
    }
  ]
}
```

Role weighting applied in scoring: CEO/CFO/President at 1.5×, Director at 1.0×, VP/other at 0.7×. Sells are counted at 40% of their notional value.

### GET /market-data/cboe/put-call-ratio
Returns recent market-wide CBOE put/call ratio rows (equity P/C ratio). Fetched daily at :12.

Query params: `?days=30` (default 30)

```json
[
  { "date": "2025-06-15", "put_call_ratio": 0.71, "fetched_at": "2025-06-15T12:15:00Z" }
]
```

---

## Articles

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/articles` | Yes | Paginated article list, filterable by source/ticker/status/event category |
| GET | `/articles/sources` | Yes | All sources with article counts |
| GET | `/articles/event-categories` | Yes | All event categories with article counts |

Query params for `/articles`: `?source=yahoo_finance&ticker=XOM&is_processed=false&event_category=earnings&page=1&per_page=20`

When `ticker` is set, only articles linked at confidence ≥ 0.60 are returned (company-name matches and above). Industry-keyword sector spray (0.45) is excluded.

### GET /articles response
```json
{
  "data": [
    {
      "id": 1,
      "source": "yahoo_finance",
      "source_url": "https://finance.yahoo.com/...",
      "title": "XOM beats earnings",
      "summary": null,
      "author": null,
      "published_at": "2025-01-15T10:00:00Z",
      "scraped_at": "2025-01-15T10:05:00Z",
      "is_processed": true,
      "event_category": "earnings",
      "duplicate_group_id": null,
      "canonical_article_id": null,
      "quality_score": 0.82,
      "llm_extracted": true,
      "metadata_": {
        "guidance_change": "positive",
        "management_tone": 0.15
      },
      "tickers": ["XOM", "CVX"]
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 150, "total_pages": 8 }
}
```

**Article field notes:**

- `quality_score` (FLOAT 0–1): composite gate score — source credibility 40%, quantitative content 25%, ticker confidence 25%, text length 10%. Signals only include articles with `quality_score ≥ 0.40`.
- `llm_extracted` (BOOL | null): `null` = extraction not attempted, `true` = Claude Haiku ran successfully, `false` = empty text or extraction failed.
- `metadata_` (JSONB): for `analyst_rating` articles contains `rating_change`, `price_target`, `analyst_firm`; for `earnings` articles contains `guidance_change`. Populated by LLM extraction when `LLM_EXTRACTION_ENABLED=true`.
- `duplicate_group_id` / `canonical_article_id`: non-canonical articles within a group are excluded from signal scoring.

### GET /articles/sources response
```json
[
  { "source": "yahoo_finance", "count": 450 },
  { "source": "sec_edgar", "count": 180 }
]
```

### GET /articles/event-categories response
```json
[
  { "category": "earnings", "count": 320 },
  { "category": "analyst_rating", "count": 150 },
  { "category": "macro_economic", "count": 180 },
  { "category": "general_news", "count": 450 }
]
```

Ten categories: `earnings`, `mergers_acquisitions`, `regulatory`, `product_launch`, `analyst_rating`, `insider_trading`, `macro_economic`, `legal`, `dividend`, `general_news`.

---

## Sentiment

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/sentiment/{ticker}` | Yes | Daily sentiment time series (averaged scores per day) |
| GET | `/sentiment/{ticker}/articles` | Yes | Paginated articles with FinBERT sentiment scores for ticker |
| GET | `/sentiment/summary/sectors` | Yes | Sector-level sentiment aggregation |
| GET | `/sentiment/trending/stocks` | Yes | Top stocks by sentiment article volume |

### GET /sentiment/{ticker}
Query params: `?days=30` (default 30)

```json
[
  {
    "date": "2025-06-15",
    "avg_positive": 0.65,
    "avg_negative": 0.15,
    "avg_neutral": 0.20,
    "article_count": 8,
    "dominant_label": "positive"
  }
]
```

### GET /sentiment/{ticker}/articles
Query params: `?page=1&per_page=20`

Only articles linked at confidence ≥ 0.60 are included (same floor as `GET /articles?ticker=`).

```json
{
  "data": [
    {
      "id": 1,
      "article_id": 42,
      "stock_id": 5,
      "label": "positive",
      "positive": 0.85,
      "negative": 0.05,
      "neutral": 0.10,
      "model_version": "ProsusAI/finbert",
      "created_at": "2025-06-15T10:00:00Z",
      "article_title": "XOM beats earnings expectations",
      "article_source": "yahoo_finance",
      "article_event_category": "earnings"
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 42, "total_pages": 3 }
}
```

### GET /sentiment/summary/sectors
Query params: `?days=7` (default 7)

```json
[
  {
    "sector": "Energy",
    "avg_positive": 0.45,
    "avg_negative": 0.25,
    "avg_neutral": 0.30,
    "total_articles": 120,
    "positive_count": 55,
    "negative_count": 30,
    "neutral_count": 35,
    "dominant_label": "positive"
  }
]
```

Results are served from a daily materialized view refreshed at :35.

### GET /sentiment/trending/stocks
Query params: `?days=3&limit=10` (defaults)

```json
[
  {
    "ticker": "XOM",
    "avg_positive": 0.70,
    "avg_negative": 0.10,
    "avg_neutral": 0.20,
    "total_articles": 25,
    "dominant_label": "positive"
  }
]
```

---

## Signals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/signals` | Yes | Paginated signals list, filterable by direction/strength/ticker/sector |
| GET | `/signals/latest` | Yes | Most recent signals across all stocks (dashboard feed) |
| GET | `/signals/accuracy` | Yes | Global or per-sector signal accuracy (per-signal outcomes) |
| GET | `/signals/accuracy/trend` | Yes | Accuracy over time in weekly/monthly buckets |
| GET | `/signals/accuracy/distribution` | Yes | Accuracy breakdown by strength and direction |
| GET | `/signals/accuracy/ml` | Yes | ML vs rule-based accuracy comparison (A/B) |
| GET | `/signals/accuracy/{ticker}` | Yes | Per-ticker accuracy across 1/3/5-day windows |
| GET | `/signals/detail/{signal_id}` | Yes | Full signal with per-signal outcomes and linked articles |
| GET | `/signals/weights` | Yes | Formula defaults + active per-sector and per-(sector, regime) weights |
| GET | `/signals/daily-views` | Yes | Paginated daily net views (one row per stock per session) |
| GET | `/signals/daily-views/today` | Yes | Today's prediction cards for the dashboard |
| GET | `/signals/{ticker}` | Yes | Signal history for a specific ticker |

Query params for `/signals`: `?direction=bullish&strength=strong&ticker=XOM&sector=energy&page=1&per_page=20`

Query params for `/signals/latest`: `?limit=20&min_strength=moderate`

### Signal object fields

```json
{
  "id": 1,
  "stock_id": 5,
  "ticker": "XOM",
  "company_name": "Exxon Mobil",
  "direction": "bullish",
  "strength": "moderate",
  "composite_score": 0.42,
  "sentiment_score": 0.35,
  "sentiment_volume_score": 0.20,
  "retail_sentiment_score": 0.10,
  "price_score": 0.15,
  "volume_score": 0.10,
  "rsi_score": 0.22,
  "trend_score": 0.18,
  "earnings_score": null,
  "options_score": null,
  "analyst_score": null,
  "insider_score": null,
  "ml_score": 0.31,
  "ml_direction": "bullish",
  "ml_confidence": 0.68,
  "has_ml": false,
  "market_regime": "sideways",
  "trading_date": "2025-06-16",
  "article_count": 8,
  "reasoning": "XOM: moderate bullish signal (score: 0.420)...",
  "generated_at": "2025-06-15T10:30:00Z",
  "window_start": "2025-06-15T09:30:00Z",
  "window_end": "2025-06-15T10:30:00Z"
}
```

**Signal field notes:**

- `market_regime`: `trending_up` | `trending_down` | `overbought` | `oversold` | `sideways` — determined by the regime multiplier logic (RSI/trend as context, not additive components).
- `trading_date` (DATE): the next session close this signal is predicting. All signals for the same stock and `trading_date` are collapsed into a `daily_signal_view`.
- `has_ml` (BOOL): `true` when `ml_score` was promoted into the live composite (model qualified: `validation_accuracy ≥ 55%` and `training_samples ≥ 50`); `false` when ML is A/B comparison only.
- `insider_score` (FLOAT | null): gated 8% component from 30-day Form 4 net buying. Null when gate is inactive.
- `analyst_score` (FLOAT | null): gated 7% component from 30-day LLM-extracted analyst ratings. Null when no qualifying articles.
- `earnings_score` (FLOAT | null): gated 10% component, active within 48h of an EPS release. Null otherwise.
- `options_score` (FLOAT | null): gated 8% component using z-score vs 20-day baseline. Null when `OPTIONS_FLOW_ENABLED` is off or no baseline.
- `retail_sentiment_score`: Reddit-only sentiment sub-score, surfaced separately for transparency but not a standalone component.
- `rsi_score` / `trend_score`: stored as raw values but their weight in the composite is 0.0 — they act as the regime multiplier context only.
- Strength thresholds: **strong** = |score| > 0.6, **moderate** > 0.35, **weak** otherwise.

### GET /signals/accuracy

Uses per-signal `signal_outcomes` table (legacy per-signal evaluation). Query params: `?window_days=5&sector=energy&days=90`

```json
[
  {
    "scope": "global",
    "window_days": 5,
    "total_evaluated": 150,
    "correct_count": 92,
    "accuracy_pct": 61.3,
    "avg_return_correct": 2.15,
    "avg_return_wrong": -1.82,
    "bullish_accuracy_pct": 63.5,
    "bearish_accuracy_pct": 58.1
  }
]
```

### GET /signals/accuracy/trend

Query params: `?window_days=5&sector=energy&bucket=week&days=180`

```json
[
  {
    "period_start": "2025-01-01T00:00:00Z",
    "period_end": "2025-01-08T00:00:00Z",
    "total": 20,
    "correct": 12,
    "accuracy_pct": 60.0
  }
]
```

### GET /signals/accuracy/distribution

Query params: `?window_days=5&days=90`

```json
{
  "by_strength": [
    { "label": "strong", "total": 10, "correct": 8, "accuracy_pct": 80.0, "avg_return_pct": 2.5 },
    { "label": "moderate", "total": 30, "correct": 18, "accuracy_pct": 60.0, "avg_return_pct": 1.2 }
  ],
  "by_direction": [
    { "label": "bullish", "total": 40, "correct": 24, "accuracy_pct": 60.0, "avg_return_pct": 1.5 },
    { "label": "bearish", "total": 40, "correct": 20, "accuracy_pct": 50.0, "avg_return_pct": -0.5 }
  ]
}
```

### GET /signals/detail/{signal_id}

```json
{
  "signal": {
    "id": 1, "ticker": "AAPL", "direction": "bullish",
    "composite_score": 0.45, "market_regime": "trending_up",
    "trading_date": "2025-01-16", "has_ml": true,
    "...": "all signal fields as above"
  },
  "outcomes": [
    {
      "window_days": 1,
      "price_change_pct": 0.012,
      "is_correct": true,
      "evaluated_at": "2025-01-16T21:00:00Z"
    },
    {
      "window_days": 5,
      "price_change_pct": 0.031,
      "is_correct": true,
      "evaluated_at": "2025-01-20T21:00:00Z"
    }
  ],
  "linked_articles": [
    {
      "id": 42,
      "title": "Apple surges on earnings beat",
      "source": "yahoo_finance",
      "url": "https://...",
      "published_at": "2025-01-15T10:00:00Z",
      "sentiment_label": "positive",
      "sentiment_score": 0.90
    }
  ]
}
```

Articles are linked via `SentimentScore.stock_id` + `processed_at` within the signal's `window_start`/`window_end`, limited to 50.

### GET /signals/weights

Returns the formula defaults, per-sector (global + all sectors), and per-(sector, regime) adaptive weights written by the daily optimizer.

`rsi` and `trend` are always 0.0 in the database — they provide regime multiplier context and are not additive components. The regime multiplier itself applies ±15% to the composite.

```json
{
  "defaults": {
    "sentiment_momentum": 0.40,
    "sentiment_volume": 0.25,
    "price_momentum": 0.20,
    "volume_anomaly": 0.15,
    "earnings": 0.10,
    "options": 0.08,
    "analyst": 0.07,
    "ml": 0.08,
    "insider": 0.08,
    "rsi": 0.0,
    "trend": 0.0,
    "strong_threshold": 0.6,
    "moderate_threshold": 0.35,
    "regime_adjustment": 0.15,
    "ml_min_accuracy": 0.55,
    "ml_min_samples": 50
  },
  "weights": [
    {
      "sector_name": null,
      "sentiment_momentum": 0.41,
      "sentiment_volume": 0.24,
      "price_momentum": 0.19,
      "volume_anomaly": 0.16,
      "rsi": 0.0,
      "trend": 0.0,
      "options": 0.08,
      "earnings": 0.10,
      "analyst": 0.07,
      "insider": 0.08,
      "sample_count": 500,
      "accuracy_pct": 58.2,
      "computed_at": "2025-06-15T04:00:00Z",
      "source": "global"
    },
    {
      "sector_name": "Technology",
      "sentiment_momentum": 0.38,
      "...": "...",
      "source": "sector"
    }
  ],
  "regime_weights": [
    {
      "sector_name": "Technology",
      "market_regime": "trending_up",
      "sentiment_momentum": 0.36,
      "sentiment_volume": 0.26,
      "price_momentum": 0.22,
      "volume_anomaly": 0.16,
      "rsi": 0.0,
      "trend": 0.0,
      "options": 0.08,
      "earnings": 0.10,
      "analyst": 0.07,
      "insider": 0.08,
      "sample_count": 80,
      "accuracy_pct": 62.5,
      "computed_at": "2025-06-15T04:00:00Z"
    }
  ]
}
```

Weight lookup priority for live scoring: `(sector, market_regime)` → `(global, market_regime)` → sector → global → defaults.

### GET /signals/daily-views

Returns paginated daily net views. Each row collapses all intra-day signals for a stock into a single session-level prediction. Signals are bucketed into 4-hour ET windows (pre_market / morning / afternoon) before netting; votes are recency-weighted toward the session close (λ = 0.15).

Query params: `?ticker=XOM&sector=energy&direction=bullish&page=1&per_page=20`

```json
{
  "data": [
    {
      "id": 10,
      "stock_id": 5,
      "ticker": "XOM",
      "company_name": "Exxon Mobil",
      "trading_date": "2025-06-16",
      "net_score": 0.38,
      "direction": "bullish",
      "strength": "moderate",
      "conviction": 0.72,
      "signal_count": 3,
      "raw_signal_count": 5,
      "majority_regime": "sideways",
      "outcome": {
        "window_days": 1,
        "price_change_pct": 0.018,
        "sector_return_pct": 0.005,
        "excess_return_pct": 0.013,
        "is_correct": true,
        "evaluated_at": "2025-06-17T21:00:00Z"
      }
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 320, "total_pages": 16 }
}
```

**Daily view field notes:**

- `net_score`: recency-weighted average of bucketed signal scores, normalized to [-1, 1].
- `conviction`: absolute net score; views with conviction < 0.20 are stored but excluded from weight/ML learning.
- `signal_count`: number of 4-hour bucket representatives that contributed to the net view.
- `raw_signal_count`: total raw signals generated for this stock on this trading date before bucketing.
- `majority_regime`: modal market_regime label across the contributing bucketed signals.
- `outcome.is_correct`: determined by excess return vs the sector ETF (XLE/XLF/XLK/XLC/XLY). For Market ETFs the absolute return is used.

### GET /signals/daily-views/today

Returns the current session's daily net views sorted by conviction, used for the Dashboard "Today's Predictions" panel. Includes live price change when market is open.

Query params: `?sector=energy&limit=20`

```json
[
  {
    "ticker": "XOM",
    "company_name": "Exxon Mobil",
    "trading_date": "2025-06-16",
    "net_score": 0.38,
    "direction": "bullish",
    "strength": "moderate",
    "conviction": 0.72,
    "signal_count": 3,
    "majority_regime": "sideways",
    "live_change_pct": 0.011
  }
]
```

`live_change_pct` is null outside market hours.

---

## Portfolio

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/portfolio/summary` | Yes | Current portfolio value, cash, unrealised P&L |
| GET | `/portfolio/positions` | Yes | Open positions with entry price, current value, P&L |
| GET | `/portfolio/trades` | Yes | Trade history (paginated) |
| GET | `/portfolio/performance` | Yes | Daily equity curve vs SPY benchmark |
| GET | `/portfolio/stats` | Yes | Sharpe ratio, max drawdown, win rate, avg win/loss, alpha, beta |

The paper portfolio is opt-in (`PAPER_PORTFOLIO_ENABLED=true`). Positions are opened at :35 when a bullish ≥ moderate signal exists (10% of MTM equity, max 10 positions, max 3 per sector) and closed on stop-loss 8% / take-profit 20% / signal reversal. A daily equity snapshot vs SPY is taken at 21:30 UTC.

### GET /portfolio/summary
```json
{
  "portfolio_id": 1,
  "name": "Paper Portfolio",
  "starting_capital": 100000.0,
  "current_equity": 107320.0,
  "cash": 62800.0,
  "positions_value": 44520.0,
  "total_return_pct": 7.32,
  "created_at": "2025-01-01T00:00:00Z"
}
```

### GET /portfolio/positions
```json
[
  {
    "id": 3,
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "sector": "Technology",
    "shares": 52,
    "entry_price": 191.50,
    "current_price": 197.30,
    "entry_value": 9958.0,
    "current_value": 10259.6,
    "unrealised_pnl": 301.6,
    "unrealised_pnl_pct": 3.03,
    "opened_at": "2025-06-10T13:35:00Z"
  }
]
```

### GET /portfolio/trades
Query params: `?page=1&per_page=20`

```json
{
  "data": [
    {
      "id": 10,
      "ticker": "AAPL",
      "action": "sell",
      "shares": 52,
      "price": 212.40,
      "value": 11044.8,
      "return_pct": 10.91,
      "exit_reason": "take_profit",
      "executed_at": "2025-06-15T13:35:00Z"
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 30, "total_pages": 2 }
}
```

Exit reasons: `stop_loss`, `take_profit`, `signal_reversal`, `end_of_day`.

### GET /portfolio/performance
```json
[
  {
    "date": "2025-06-10",
    "equity": 103200.0,
    "spy_equity": 102100.0
  }
]
```

### GET /portfolio/stats
```json
{
  "sharpe_ratio": 1.21,
  "max_drawdown_pct": -4.83,
  "win_rate_pct": 62.5,
  "avg_win_pct": 4.20,
  "avg_loss_pct": -2.10,
  "total_trades": 24,
  "open_positions": 3,
  "alpha": 2.1,
  "beta": 0.87
}
```

---

## Alerts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/alerts/configs` | Yes | User's alert configurations |
| POST | `/alerts/configs` | Yes | Create alert config (201) |
| PUT | `/alerts/configs/{id}` | Yes | Update alert config |
| DELETE | `/alerts/configs/{id}` | Yes | Delete alert config (204) |
| GET | `/alerts/history` | Yes | Sent alert log (paginated) |
| POST | `/alerts/test` | Yes | Send test alert to verify channel config |

### POST /alerts/configs
```json
// Request
{
  "stock_id": null,
  "min_strength": "moderate",
  "direction_filter": ["bullish"],
  "channel": "discord"
}

// Response (201)
{
  "id": 1,
  "user_id": 1,
  "stock_id": null,
  "ticker": null,
  "min_strength": "moderate",
  "direction_filter": ["bullish"],
  "channel": "discord",
  "is_active": true,
  "created_at": "2025-06-15T10:00:00Z"
}
```

### POST /alerts/test
```json
// Request
{ "channel": "discord" }

// Response
{ "success": true, "message": "discord: sent successfully" }
```

---

## Watchlist

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/watchlist` | Yes | User's watchlist with stock details and 30-day sparkline |
| POST | `/watchlist` | Yes | Add ticker (201) |
| DELETE | `/watchlist/{ticker}` | Yes | Remove from watchlist (204) |

```json
// POST /watchlist request
{ "ticker": "XOM" }
```

---

## Backtests

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/backtests` | Yes | Create and queue a backtest job (201) |
| GET | `/backtests` | Yes | List user's backtests (paginated, filterable by status) |
| GET | `/backtests/{id}` | Yes | Backtest detail with equity curve, trades, and benchmark |
| DELETE | `/backtests/{id}` | Yes | Delete own backtest (204, cascades trades) |
| GET | `/backtests/{id}/export` | Yes | Export trades or equity curve as CSV download |

### POST /backtests
```json
// Request
{
  "ticker": "AAPL",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "starting_capital": 10000,
  "mode": "technical",
  "min_signal_strength": "moderate",
  "commission_pct": 0.001,
  "slippage_pct": 0.0005,
  "position_size_pct": 100.0,
  "stop_loss_pct": 5.0,
  "take_profit_pct": 20.0,
  "benchmark_ticker": "SPY"
}

// Sector-level backtest (use sector_name instead of ticker):
{ "sector_name": "Technology", "mode": "full", "min_signal_strength": "strong", "..." }

// Response (201) — status will be "pending" initially
{
  "id": 1, "user_id": 1, "ticker": "AAPL", "sector_name": null,
  "mode": "technical", "status": "pending",
  "start_date": "2020-01-01", "end_date": "2024-12-31",
  "starting_capital": 10000.0, "min_signal_strength": "moderate",
  "commission_pct": 0.001, "slippage_pct": 0.0005,
  "position_size_pct": 100.0, "stop_loss_pct": 5.0, "take_profit_pct": 20.0,
  "benchmark_ticker": "SPY",
  "total_return_pct": null, "annualized_return_pct": null,
  "sharpe_ratio": null, "max_drawdown_pct": null,
  "win_rate_pct": null, "total_trades": null,
  "benchmark_total_return_pct": null, "benchmark_annualized_return_pct": null,
  "alpha": null, "beta": null,
  "created_at": "2025-06-15T10:00:00Z", "completed_at": null
}
```

Validation:
- Exactly one of `ticker` or `sector_name` required
- `start_date` must be before `end_date`; neither may be in the future
- `starting_capital`: $100–$1,000,000 (default $10,000)
- `mode`: `"technical"` (OHLCV + regime signals, no historical sentiment) or `"full"` (adds stored sentiment; earnings/options not replayed)
- `min_signal_strength`: `"moderate"` or `"strong"`
- `commission_pct`: 0–5% (default 0.1%)
- `slippage_pct`: 0–5% (default 0.05%)
- `position_size_pct`: 10–100% (default 100%)
- `stop_loss_pct`: 0–50% or null
- `take_profit_pct`: 0–500% or null
- `benchmark_ticker`: any valid ticker (default SPY)

Backtests always set `has_ml = false` — ML models are not replayed to avoid look-ahead bias.

### GET /backtests
Query params: `?status=completed&page=1&per_page=20`

### GET /backtests/{id}
```json
{
  "id": 1, "ticker": "AAPL", "sector_name": null,
  "mode": "technical", "status": "completed",
  "commission_pct": 0.001, "slippage_pct": 0.0005,
  "position_size_pct": 100.0, "stop_loss_pct": 5.0, "take_profit_pct": 20.0,
  "benchmark_ticker": "SPY",
  "total_return_pct": 42.5, "annualized_return_pct": 8.2,
  "sharpe_ratio": 1.15, "max_drawdown_pct": -12.3,
  "win_rate_pct": 58.0, "total_trades": 24,
  "avg_win_pct": 5.2, "avg_loss_pct": -3.1,
  "best_trade_pct": 15.4, "worst_trade_pct": -8.7,
  "final_equity": 14250.0,
  "benchmark_total_return_pct": 35.2, "benchmark_annualized_return_pct": 6.8,
  "alpha": 1.4, "beta": 0.92,
  "equity_curve": [
    { "date": "2020-03-01", "equity": 10000.0 },
    { "date": "2020-03-02", "equity": 10050.0 }
  ],
  "benchmark_equity_curve": [
    { "date": "2020-03-01", "equity": 10000.0 },
    { "date": "2020-03-02", "equity": 10020.0 }
  ],
  "trades": [
    {
      "id": 1, "ticker": "AAPL", "action": "buy",
      "trade_date": "2020-04-15", "price": 65.50, "shares": 152,
      "position_value": 9956.0, "portfolio_equity": 10000.0,
      "signal_score": 0.48, "signal_direction": "bullish",
      "signal_strength": "moderate", "return_pct": null, "exit_reason": null
    },
    {
      "id": 2, "ticker": "AAPL", "action": "sell",
      "trade_date": "2020-05-20", "price": 72.30, "shares": 152,
      "position_value": 10990.0, "portfolio_equity": 10990.0,
      "signal_score": -0.45, "signal_direction": "bearish",
      "signal_strength": "moderate", "return_pct": 10.2, "exit_reason": "signal"
    }
  ],
  "created_at": "...", "completed_at": "..."
}
```

Exit reasons: `signal`, `stop_loss`, `take_profit`, `end_of_period`.

### GET /backtests/{id}/export
Query params: `?type=trades` or `?type=equity_curve`

Returns a CSV file as an attachment download.

---

## Admin

All admin endpoints require an admin JWT (`is_admin = true`). All POST endpoints return **202 Accepted** (task queued) and are recorded in the audit log.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/admin/seed-history` | Admin | Trigger historical OHLCV backfill (Celery, `signals` queue) |
| POST | `/admin/scrape-now` | Admin | Trigger immediate scrape orchestration |
| POST | `/admin/maintenance` | Admin | Trigger data maintenance (compression, cleanup, purge) |
| POST | `/admin/evaluate-outcomes` | Admin | Trigger signal and daily-view outcome evaluation |
| POST | `/admin/compute-weights` | Admin | Trigger adaptive weight computation |
| POST | `/admin/backfill-event-categories` | Admin | Classify articles without an event_category |
| POST | `/admin/backfill-duplicate-groups` | Admin | Run fuzzy duplicate detection (last N days) |
| POST | `/admin/train-ml-models` | Admin | Trigger per-sector LightGBM model training |
| POST | `/admin/fetch-options` | Admin | Trigger options chain data fetch for all tickers |
| POST | `/admin/fetch-insider` | Admin | Trigger Form 4 insider transaction scrape |
| POST | `/admin/reset-learning-layer` | Admin | Truncate learning layer tables (202, idempotent) |
| GET | `/admin/ml-models` | Admin | ML model status per sector |
| GET | `/admin/task-failures` | Admin | Dead letter queue (paginated) |
| POST | `/admin/task-failures/{id}/retry` | Admin | Re-queue a failed Celery task |
| GET | `/admin/audit-log` | Admin | Admin audit log (paginated) |
| GET | `/admin/db-stats` | Admin | Table row counts and sizes |

### POST /admin/seed-history
Query params: `?period=max` (options: `max`, `10y`, `5y`, `2y`, `1y`; default `max`)

```json
// Response (202)
{ "task_id": "abc-123", "period": "max", "status": "queued" }
```

### POST /admin/scrape-now
```json
// Response (202)
{ "task_id": "def-456", "status": "queued" }
```

### POST /admin/maintenance
```json
// Response (202)
{ "task_id": "ghi-789", "status": "queued" }
```

### POST /admin/evaluate-outcomes
```json
// Response (202)
{ "task_id": "jkl-012", "status": "queued" }
```

### POST /admin/compute-weights
```json
// Response (202)
{ "task_id": "mno-345", "status": "queued" }
```

### POST /admin/train-ml-models
Requires `ML_ENSEMBLE_ENABLED=true` on the compute VM. Trains per-sector and global fallback LightGBM classifiers from 1-day daily-view outcomes (conviction ≥ 0.20).

```json
// Response (202)
{ "task_id": "pqr-678", "status": "queued" }
```

### POST /admin/fetch-options
Requires `OPTIONS_FLOW_ENABLED=true`. Fetches yfinance options chains for all active tickers and the CBOE put/call ratio.

```json
// Response (202)
{ "task_id": "stu-901", "status": "queued" }
```

### POST /admin/fetch-insider
Requires `INSIDER_FLOW_ENABLED=true`. Fetches yfinance Form 4 insider transactions for all active tickers.

```json
// Response (202)
{ "task_id": "vwx-234", "status": "queued" }
```

### POST /admin/reset-learning-layer

Truncates all learning-layer tables so the system can start fresh:
- `daily_signal_view_outcomes` — daily-view 1/3/5-day outcome evaluations
- `signal_outcomes` — per-signal outcome evaluations (legacy)
- `ml_models` — all trained LightGBM model records
- `signal_weights` — all per-sector adaptive weights
- `regime_adaptive_weights` — all per-(sector, regime) adaptive weights

The operation is idempotent (safe to call on an already-empty learning layer). All admin actions including this one are recorded in `audit_logs`.

```json
// Response (202)
{ "status": "ok", "message": "Learning layer reset successfully" }
```

### GET /admin/ml-models
```json
[
  {
    "id": 1,
    "sector_name": "Technology",
    "model_version": "v3",
    "training_samples": 180,
    "validation_accuracy": 0.623,
    "f1_score": 0.61,
    "feature_importances": {
      "sentiment_momentum": 0.31,
      "price_momentum": 0.22,
      "sentiment_volume": 0.18,
      "volume_anomaly": 0.14,
      "earnings": 0.09,
      "options": 0.06
    },
    "trained_at": "2025-06-15T04:30:00Z",
    "is_active": true
  }
]
```

Models with `validation_accuracy ≥ 0.55` and `training_samples ≥ 50` are eligible to promote `ml_score` into the live composite (`has_ml = true` on signals).

### GET /admin/task-failures
Query params: `?task_name=worker.tasks.scraping&page=1&per_page=20`

```json
{
  "data": [
    {
      "id": 1,
      "task_name": "worker.tasks.scraping.yahoo_finance",
      "exception_type": "ConnectionError",
      "exception_message": "Connection refused",
      "failed_at": "2025-06-15T10:00:00Z",
      "retries_exhausted": true,
      "retried_at": null,
      "retry_task_id": null
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 5, "total_pages": 1 }
}
```

### POST /admin/task-failures/{id}/retry
Re-queues the failed task via `send_task()` using the original task name and kwargs.

```json
// Response (202)
{ "task_id": "new-abc-123", "status": "queued" }
```

### GET /admin/audit-log
Query params: `?action=trigger_scrape&page=1&per_page=20`

```json
{
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "action": "trigger_scrape",
      "resource": "admin/scrape-now",
      "detail": null,
      "ip_address": "192.168.1.1",
      "created_at": "2025-06-15T10:00:00Z"
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 50, "total_pages": 3 }
}
```

Audit log entries are retained for 90 days (cleaned by daily maintenance task).

### GET /admin/db-stats
```json
[
  { "table": "articles", "row_count": 15000, "size": "45 MB" },
  { "table": "sentiment_scores", "row_count": 8500, "size": "12 MB" },
  { "table": "signals", "row_count": 4200, "size": "8 MB" },
  { "table": "daily_signal_views", "row_count": 1100, "size": "2 MB" }
]
```

---

## API Keys

Managed under `/auth/api-keys`. See the Authentication section above for full documentation of `POST`, `GET`, and `DELETE /auth/api-keys`.

API keys:
- Prefixed with `sp_` followed by 32 hex characters
- Stored as SHA-256 hashes — the raw key is returned only on creation
- Max 5 active keys per user
- Soft-revoked (`is_active = false`) via DELETE; the key record is retained
- Optional expiry (`expires_in_days`); expired keys are rejected on auth
- Accepted in the `Authorization: Bearer sp_...` header — the same header used for JWT tokens

---

## Dashboard Data Sources

The dashboard is composed on the frontend from existing endpoints. There is no dedicated `/dashboard` backend route. The frontend parallelises these calls via TanStack Query:

| Panel | Source endpoint |
|-------|----------------|
| Today's Predictions | `GET /signals/daily-views/today` |
| Latest Signals feed | `GET /signals/latest?min_strength=moderate&limit=10` |
| Sector Heatmap | `GET /sentiment/summary/sectors` |
| Top Movers | `GET /signals/latest` (client-side sort by composite score) |
| Article Activity | `GET /articles/sources` |

---

## Signal Scoring Reference

```
composite = 0.40 * sentiment_momentum
          + 0.25 * sentiment_volume
          + 0.20 * price_momentum
          + 0.15 * volume_anomaly
          + 0.10 * earnings_score   (gated — 48h EPS window; guidance_change ±0.20, management_tone ±0.10)
          + 0.08 * options_score    (gated — OPTIONS_FLOW_ENABLED, z-score vs 20-day baseline)
          + 0.07 * analyst_score    (gated — 30-day LLM-extracted analyst ratings)
          + 0.08 * ml_score         (gated — model accuracy ≥ 55% and training_samples ≥ 50)
          + 0.08 * insider_score    (gated — 30-day Form 4 net buying, INSIDER_FLOW_ENABLED)

regime multiplier = ±15% applied via apply_regime_multiplier(composite, rsi_score, trend_score):
  Priority 1: |rsi_score| > 0.4  → dampen 15%, regime = overbought | oversold
  Priority 2: strong trend confirming signal  → boost 15%, regime = trending_up | trending_down
  Priority 3: strong trend opposing signal    → dampen 15%
  Default: regime = sideways
```

Component formulas:
- `rsi_score = tanh((50 - rsi) / 50 * 2.5)` — oversold → positive
- `trend_score = 0.6 * sma_crossover + 0.4 * macd_histogram_signal`
- `options_score = 0.6 * -tanh(pcr_z) + 0.4 * -tanh(skew_z)`
- `earnings_score = tanh(surprise_pct / 5.0)` + guidance_change ±0.20 + management_tone ±0.10
- `analyst_score = 0.6 * tanh(net_rating / 2) + 0.4 * tanh(mean_upside * 5)`
- `insider_score = tanh(net_value / 500_000)` — sells counted at 40%

Weights are adaptive: the daily 4 AM optimizer writes per-(sector, regime) and per-sector weights from return-weighted 1-day daily-view outcomes. Conviction threshold for learning: `|net_score| ≥ 0.20`. `is_correct` is excess return vs sector ETF (XLE/XLF/XLK/XLC/XLY); Market ETFs use absolute return.
