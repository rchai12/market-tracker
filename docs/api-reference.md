# API Reference

Base URL: `/api`

All protected endpoints require `Authorization: Bearer <token>` header.

## Response Envelope

All list endpoints return:
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

## Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Create new account |
| POST | `/auth/login` | No | Login (OAuth2 form) |
| POST | `/auth/refresh` | No | Refresh access token |
| GET | `/auth/me` | Yes | Get current user profile |

### POST /auth/register
```json
// Request
{ "email": "user@example.com", "username": "user", "password": "secret" }

// Response
{ "user": { "id": 1, "email": "...", "username": "..." }, "access_token": "...", "refresh_token": "..." }
```

### POST /auth/login
```
// Request (form-urlencoded)
username=user@example.com&password=secret

// Response
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "user": { ... } }
```

## Stocks

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/stocks` | Yes | List stocks (paginated, filterable) |
| GET | `/stocks/{ticker}` | Yes | Stock detail with latest sentiment + signal |

Query params for `/stocks`: `?sector=energy&search=exxon&page=1&per_page=20`

## Market Data

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/market-data/{ticker}/daily` | Yes | Daily OHLCV |
| GET | `/market-data/{ticker}/intraday` | Yes | Intraday data |

Query params: `?start_date=2025-01-01&end_date=2025-12-31&limit=365`

## Sentiment

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/sentiment/{ticker}` | Yes | Sentiment time series |
| GET | `/sentiment/{ticker}/articles` | Yes | Articles with scores for ticker |
| GET | `/sentiment/summary` | Yes | Sector-level aggregation |
| GET | `/sentiment/trending` | Yes | Highest sentiment volume/change |

## Signals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/signals` | Yes | All signals (paginated, filterable) |
| GET | `/signals/{ticker}` | Yes | Signal history for ticker |
| GET | `/signals/latest` | Yes | Most recent signals (dashboard feed) |

Query params: `?direction=bullish&strength=strong&ticker=XOM&page=1`

## Alerts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/alerts/configs` | Yes | User's alert configurations |
| POST | `/alerts/configs` | Yes | Create alert config |
| PUT | `/alerts/configs/{id}` | Yes | Update alert config |
| DELETE | `/alerts/configs/{id}` | Yes | Delete alert config |
| GET | `/alerts/history` | Yes | Sent alert log |
| POST | `/alerts/test` | Yes | Send test alert |

## Watchlist

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/watchlist` | Yes | User's watchlist with latest data |
| POST | `/watchlist` | Yes | Add ticker to watchlist |
| DELETE | `/watchlist/{ticker}` | Yes | Remove from watchlist |

## Dashboard

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/dashboard/overview` | Yes | Sector heatmap, top signals, market summary |
| GET | `/dashboard/top-movers` | Yes | Top 5 bullish + bearish |

## Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/scrape-logs` | Admin | Scrape execution history |
| POST | `/admin/scrape/trigger` | Admin | Manually trigger scrape cycle |
| GET | `/admin/system/health` | Admin | Service health: DB, Redis, workers |

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Basic health check |
