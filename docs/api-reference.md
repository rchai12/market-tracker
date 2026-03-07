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

Query params: `?start_date=2025-01-01&end_date=2025-12-31&limit=365`

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
| GET | `/signals` | Yes | **Done** | All signals (paginated, filterable by direction/strength/ticker) |
| GET | `/signals/latest` | Yes | **Done** | Most recent signals across all stocks (dashboard feed) |
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
    "article_count": 8, "reasoning": "XOM: moderate bullish signal (score: 0.420)...",
    "generated_at": "2025-06-15T10:30:00Z",
    "window_start": "2025-06-15T09:30:00Z", "window_end": "2025-06-15T10:30:00Z"
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
