# API Reference

Base URL: `/api`

All protected endpoints require `Authorization: Bearer <token>` header.

Status legend: **Done** = implemented, **Planned** = not yet built.

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

Single-item endpoints return the object directly.

## Health

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/health` | No | **Done** | Basic health check |

## Authentication

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| POST | `/auth/register` | No | **Done** | Create new account |
| POST | `/auth/login` | No | **Done** | Login (OAuth2 form, username field = email) |
| POST | `/auth/refresh` | No | **Done** | Refresh access token |
| GET | `/auth/me` | Yes | **Done** | Get current user profile |
| PUT | `/auth/profile` | Yes | **Done** | Update username and/or email |
| PUT | `/auth/password` | Yes | **Done** | Change password |

### POST /auth/register
```json
// Request
{ "email": "user@example.com", "username": "user", "password": "secret" }

// Response (201)
{ "user": { "id": 1, "email": "...", "username": "...", "is_active": true, "is_admin": false },
  "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### POST /auth/login
```
// Request (application/x-www-form-urlencoded)
username=user@example.com&password=secret

// Response
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer",
  "user": { "id": 1, "email": "...", "username": "...", "is_active": true, "is_admin": false } }
```

### POST /auth/refresh
```json
// Request
{ "refresh_token": "..." }

// Response — same as login
```

### PUT /auth/profile
```json
// Request (all fields optional, at least one required)
{ "username": "newname", "email": "new@example.com" }

// Response
{ "id": 1, "email": "new@example.com", "username": "newname", "is_active": true, "is_admin": false }
```

Validation:
- Username: 3-50 characters (same rules as registration)
- Email: valid email format
- Both must be unique across all users (409 if taken)

### PUT /auth/password
```json
// Request
{ "current_password": "oldSecret1", "new_password": "newSecret1" }

// Response
{ "message": "Password updated" }
```

Validation:
- `current_password` must match existing password (401 if incorrect)
- `new_password`: min 8 chars, at least one uppercase, one lowercase, one digit

## Stocks

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/stocks` | Yes | **Done** | List stocks (paginated, filterable by sector/search) |
| GET | `/stocks/sectors` | Yes | **Done** | List active sector names |
| GET | `/stocks/{ticker}` | Yes | **Done** | Stock detail with sector and industry |

Query params for `/stocks`: `?sector=energy&search=exxon&page=1&per_page=20`

## Market Data

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/market-data/{ticker}/daily` | Yes | **Done** | Daily OHLCV |
| GET | `/market-data/{ticker}/intraday` | Yes | **Done** | Intraday data |
| GET | `/market-data/{ticker}/indicators` | Yes | **Done** | Technical indicators (SMA, RSI, MACD, Bollinger Bands) |

Query params for `/market-data/{ticker}/daily`: `?start_date=2025-01-01&end_date=2025-12-31&limit=365`

### GET /market-data/{ticker}/indicators

Computes technical indicators on-the-fly from stored OHLCV data. Fetches extra rows for warmup so early values are accurate.

Query params: `?days=365` (default 365)

```json
// Response
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

## Articles

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/articles` | Yes | **Done** | List articles (paginated, filterable) |
| GET | `/articles/sources` | Yes | **Done** | List sources with article counts |

Query params for `/articles`: `?source=yahoo_finance&ticker=XOM&is_processed=false&page=1&per_page=20`

### GET /articles response
```json
{
  "data": [
    {
      "id": 1, "source": "yahoo_finance", "source_url": "https://...",
      "title": "XOM beats earnings", "summary": null, "author": null,
      "published_at": "2025-01-15T10:00:00Z", "scraped_at": "2025-01-15T10:05:00Z",
      "is_processed": false, "event_category": null,
      "tickers": ["XOM", "CVX"]
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 150, "total_pages": 8 }
}
```

### GET /articles/sources response
```json
[
  { "source": "yahoo_finance", "count": 450 },
  { "source": "reuters", "count": 230 },
  { "source": "sec_edgar", "count": 180 }
]
```

## Sentiment

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/sentiment/{ticker}` | Yes | **Done** | Daily sentiment time series (avg scores per day) |
| GET | `/sentiment/{ticker}/articles` | Yes | **Done** | Paginated articles with sentiment scores for ticker |
| GET | `/sentiment/summary/sectors` | Yes | **Done** | Sector-level sentiment aggregation with label counts |
| GET | `/sentiment/trending/stocks` | Yes | **Done** | Top stocks by sentiment article volume |

### GET /sentiment/{ticker}

Query params: `?days=30` (default 30)

```json
// Response
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

```json
{
  "data": [
    {
      "id": 1, "article_id": 42, "stock_id": 5,
      "label": "positive", "positive": 0.85, "negative": 0.05, "neutral": 0.10,
      "model_version": "ProsusAI/finbert",
      "created_at": "2025-06-15T10:00:00Z",
      "article_title": "XOM beats earnings expectations",
      "article_source": "yahoo_finance"
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
    "avg_positive": 0.45, "avg_negative": 0.25, "avg_neutral": 0.30,
    "total_articles": 120,
    "positive_count": 55, "negative_count": 30, "neutral_count": 35,
    "dominant_label": "positive"
  }
]
```

### GET /sentiment/trending/stocks

Query params: `?days=3&limit=10` (defaults)

```json
[
  {
    "ticker": "XOM",
    "avg_positive": 0.70, "avg_negative": 0.10, "avg_neutral": 0.20,
    "total_articles": 25,
    "dominant_label": "positive"
  }
]
```

## Signals

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/signals` | Yes | **Done** | All signals (paginated, filterable by direction/strength/ticker/sector) |
| GET | `/signals/latest` | Yes | **Done** | Most recent signals across all stocks (dashboard feed) |
| GET | `/signals/accuracy` | Yes | **Done** | Global or sector signal accuracy metrics |
| GET | `/signals/accuracy/{ticker}` | Yes | **Done** | Per-ticker accuracy across 1/3/5 day windows |
| GET | `/signals/weights` | Yes | **Done** | Active signal weights (per-sector and global fallback) |
| GET | `/signals/{ticker}` | Yes | **Done** | Signal history for a specific ticker |

Query params for `/signals`: `?direction=bullish&strength=strong&ticker=XOM&sector=energy&page=1&per_page=20`

Query params for `/signals/latest`: `?limit=20&min_strength=moderate`

### GET /signals/latest response
```json
[
  {
    "id": 1, "stock_id": 5, "ticker": "XOM", "company_name": "Exxon Mobil",
    "direction": "bullish", "strength": "moderate",
    "composite_score": 0.42, "sentiment_score": 0.35, "price_score": 0.15, "volume_score": 0.10,
    "rsi_score": 0.22, "trend_score": 0.18,
    "article_count": 8, "reasoning": "XOM: moderate bullish signal (score: 0.420)...",
    "generated_at": "2025-06-15T10:30:00Z",
    "window_start": "2025-06-15T09:30:00Z", "window_end": "2025-06-15T10:30:00Z"
  }
]
```

### GET /signals/accuracy

Query params: `?window_days=5&sector=energy&days=90`

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

### GET /signals/weights
```json
[
  {
    "sector_name": null,
    "sentiment_momentum": 0.30, "sentiment_volume": 0.20,
    "price_momentum": 0.15, "volume_anomaly": 0.10,
    "rsi": 0.15, "trend": 0.10,
    "sample_count": 500, "accuracy_pct": 58.2,
    "computed_at": "2025-06-15T04:00:00Z", "source": "global"
  }
]
```

## Alerts

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/alerts/configs` | Yes | **Done** | User's alert configurations |
| POST | `/alerts/configs` | Yes | **Done** | Create alert config (201) |
| PUT | `/alerts/configs/{id}` | Yes | **Done** | Update alert config |
| DELETE | `/alerts/configs/{id}` | Yes | **Done** | Delete alert config (204) |
| GET | `/alerts/history` | Yes | **Done** | Sent alert log (paginated) |
| POST | `/alerts/test` | Yes | **Done** | Send test alert to verify channel config |

### POST /alerts/configs
```json
// Request
{ "stock_id": null, "min_strength": "moderate", "direction_filter": ["bullish"], "channel": "discord" }

// Response (201)
{ "id": 1, "user_id": 1, "stock_id": null, "ticker": null,
  "min_strength": "moderate", "direction_filter": ["bullish"],
  "channel": "discord", "is_active": true, "created_at": "..." }
```

### POST /alerts/test
```json
// Request
{ "channel": "discord" }

// Response
{ "success": true, "message": "discord: sent successfully" }
```

## Watchlist

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/watchlist` | Yes | **Done** | User's watchlist with stock details |
| POST | `/watchlist` | Yes | **Done** | Add ticker to watchlist `{ "ticker": "XOM" }` |
| DELETE | `/watchlist/{ticker}` | Yes | **Done** | Remove from watchlist (204) |

## Backtests

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| POST | `/backtests` | Yes | **Done** | Create and queue a backtest (201) |
| GET | `/backtests` | Yes | **Done** | List user's backtests (paginated, filterable by status) |
| GET | `/backtests/{id}` | Yes | **Done** | Backtest detail with equity curve and trade log |
| DELETE | `/backtests/{id}` | Yes | **Done** | Delete own backtest (204, cascades trades) |

### POST /backtests
```json
// Request
{
  "ticker": "AAPL",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "starting_capital": 10000,
  "mode": "technical",
  "min_signal_strength": "moderate"
}

// Or for sector backtest:
{
  "sector_name": "Technology",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "mode": "full",
  "min_signal_strength": "strong"
}

// Response (201)
{
  "id": 1, "user_id": 1, "ticker": "AAPL", "sector_name": null,
  "mode": "technical", "status": "pending",
  "start_date": "2020-01-01", "end_date": "2024-12-31",
  "starting_capital": 10000.0, "min_signal_strength": "moderate",
  "total_return_pct": null, "annualized_return_pct": null,
  "sharpe_ratio": null, "max_drawdown_pct": null,
  "win_rate_pct": null, "total_trades": null,
  "created_at": "2025-06-15T10:00:00Z", "completed_at": null
}
```

Validation:
- Exactly one of `ticker` or `sector_name` required
- `start_date` must be before `end_date`, neither can be in the future
- `starting_capital`: $100–$1,000,000 (default $10,000)
- `mode`: `"technical"` (OHLCV only) or `"full"` (+ sentiment)
- `min_signal_strength`: `"moderate"` or `"strong"`

### GET /backtests

Query params: `?status=completed&page=1&per_page=20`

### GET /backtests/{id}
```json
// Response
{
  "id": 1, "ticker": "AAPL", "sector_name": null,
  "mode": "technical", "status": "completed",
  "total_return_pct": 42.5, "annualized_return_pct": 8.2,
  "sharpe_ratio": 1.15, "max_drawdown_pct": -12.3,
  "win_rate_pct": 58.0, "total_trades": 24,
  "avg_win_pct": 5.2, "avg_loss_pct": -3.1,
  "best_trade_pct": 15.4, "worst_trade_pct": -8.7,
  "final_equity": 14250.0,
  "equity_curve": [
    { "date": "2020-03-01", "equity": 10000.0 },
    { "date": "2020-03-02", "equity": 10050.0 }
  ],
  "trades": [
    {
      "id": 1, "ticker": "AAPL", "action": "buy",
      "trade_date": "2020-04-15", "price": 65.5, "shares": 152,
      "position_value": 9956.0, "portfolio_equity": 10000.0,
      "signal_score": 0.48, "signal_direction": "bullish",
      "signal_strength": "moderate", "return_pct": null
    }
  ],
  "created_at": "...", "completed_at": "..."
}
```

## Dashboard

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/dashboard/overview` | Yes | **Deferred** | Composed from existing endpoints on frontend |
| GET | `/dashboard/top-movers` | Yes | **Deferred** | Composed from existing endpoints on frontend |

> Dashboard data is composed on the frontend from `/signals/latest`, `/sentiment/summary/sectors`,
> and `/articles/sources`. Dedicated backend endpoints deferred — frontend parallelizes queries via TanStack Query.

## Admin

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| POST | `/admin/seed-history` | Admin | **Done** | Trigger historical market data backfill (Celery task) |
| POST | `/admin/scrape-now` | Admin | **Done** | Trigger immediate scrape orchestration (Celery task) |
| POST | `/admin/maintenance` | Admin | **Done** | Trigger data maintenance (compression, cleanup, purge) |
| POST | `/admin/evaluate-outcomes` | Admin | **Done** | Trigger signal outcome evaluation (Celery task) |
| POST | `/admin/compute-weights` | Admin | **Done** | Trigger adaptive weight computation (Celery task) |
| GET | `/admin/db-stats` | Admin | **Done** | Database stats (row counts, table sizes) |

### POST /admin/seed-history
```
// Query params: ?period=max (default), 10y, 5y, 2y, 1y
// Response
{ "task_id": "abc-123", "period": "max", "status": "queued" }
```

### POST /admin/scrape-now
```
// Response
{ "task_id": "def-456", "status": "queued" }
```

### POST /admin/backtest trigger (via Celery)

Backtests are queued automatically when created via `POST /backtests`. The Celery task `worker.tasks.signals.backtest_task.run_backtest_task` runs on the `signals` queue. Manual trigger:

```bash
.venv/bin/celery -A worker.celery_app call worker.tasks.signals.backtest_task.run_backtest_task --args='[1]' --queue signals
```

### POST /admin/maintenance
```
// Response
{ "task_id": "ghi-789", "status": "queued" }
```

### GET /admin/db-stats
```json
// Response
[
  { "table": "articles", "row_count": 15000, "size": "45 MB" },
  { "table": "sentiment_scores", "row_count": 8500, "size": "12 MB" }
]
```
