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
| GET | `/stocks/{ticker}` | Yes | **Done** | Stock detail (latest sentiment + signal TBD) |

Query params for `/stocks`: `?sector=energy&search=exxon&page=1&per_page=20`

## Market Data

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/market-data/{ticker}/daily` | Yes | Planned (Phase 3) | Daily OHLCV |
| GET | `/market-data/{ticker}/intraday` | Yes | Planned (Phase 3) | Intraday data |

Query params: `?start_date=2025-01-01&end_date=2025-12-31&limit=365`

## Sentiment

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/sentiment/{ticker}` | Yes | Planned (Phase 5) | Sentiment time series |
| GET | `/sentiment/{ticker}/articles` | Yes | Planned (Phase 5) | Articles with scores for ticker |
| GET | `/sentiment/summary` | Yes | Planned (Phase 5) | Sector-level aggregation |
| GET | `/sentiment/trending` | Yes | Planned (Phase 5) | Highest sentiment volume/change |

## Signals

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/signals` | Yes | Planned (Phase 6) | All signals (paginated, filterable) |
| GET | `/signals/{ticker}` | Yes | Planned (Phase 6) | Signal history for ticker |
| GET | `/signals/latest` | Yes | Planned (Phase 6) | Most recent signals (dashboard feed) |

Query params: `?direction=bullish&strength=strong&ticker=XOM&page=1`

## Alerts

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/alerts/configs` | Yes | Planned (Phase 6) | User's alert configurations |
| POST | `/alerts/configs` | Yes | Planned (Phase 6) | Create alert config |
| PUT | `/alerts/configs/{id}` | Yes | Planned (Phase 6) | Update alert config |
| DELETE | `/alerts/configs/{id}` | Yes | Planned (Phase 6) | Delete alert config |
| GET | `/alerts/history` | Yes | Planned (Phase 6) | Sent alert log |
| POST | `/alerts/test` | Yes | Planned (Phase 6) | Send test alert |

## Watchlist

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/watchlist` | Yes | **Done** | User's watchlist with stock details |
| POST | `/watchlist` | Yes | **Done** | Add ticker to watchlist `{ "ticker": "XOM" }` |
| DELETE | `/watchlist/{ticker}` | Yes | **Done** | Remove from watchlist (204) |

## Dashboard

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/dashboard/overview` | Yes | Planned (Phase 7) | Sector heatmap, top signals, market summary |
| GET | `/dashboard/top-movers` | Yes | Planned (Phase 7) | Top 5 bullish + bearish |

## Admin

| Method | Path | Auth | Status | Description |
|--------|------|------|--------|-------------|
| GET | `/admin/scrape-logs` | Admin | Planned (Phase 4) | Scrape execution history |
| POST | `/admin/scrape/trigger` | Admin | Planned (Phase 4) | Manually trigger scrape cycle |
| GET | `/admin/system/health` | Admin | Planned (Phase 8) | Service health: DB, Redis, workers |
