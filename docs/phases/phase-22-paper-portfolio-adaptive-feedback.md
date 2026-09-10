# Phase 22 — Live Paper Portfolio + Adaptive Feedback

**Goal:** Answer the core research question — "is the system beating the market?" — with a
continuously-updated simulated portfolio driven entirely by live signals. Simultaneously
upgrade the self-adjustment loop: return-weighted outcome scoring, regime-conditional weights,
and `analyst_score` integration into the optimizer. Both halves reinforce each other: the
portfolio produces richer performance data; the feedback loop uses it to self-correct.

This phase can be delivered in two sequential milestones:
- **22a:** Paper portfolio (DB + tasks + API + frontend)
- **22b:** Smarter feedback loop (return-weighted outcomes, regime weights, analyst in optimizer)

---

## Background

The existing feedback loop:
- `outcome_evaluator.py` records directional accuracy (binary `is_correct`) at 1/3/5-day windows
- `weight_optimizer.py` uses that binary signal to compute per-sector component weights daily

Gaps:
1. Binary accuracy ignores magnitude — a component correct on a 5% move gets the same credit
   as one correct on a 0.1% move
2. Weights are sector-level only — regime is not factored in despite being tracked on every signal
3. `analyst_score` is not yet in the weight optimizer's component tracking
4. There is no portfolio-level view — only per-signal accuracy, which misses correlation,
   concentration, and compound effects

---

## Part 1 — Live Paper Portfolio (Milestone 22a)

### 1.1 Database schema

**Alembic revision:** `015_paper_portfolio.py`

```sql
CREATE TABLE paper_portfolios (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT now(),
    inception_date  DATE        NOT NULL,
    starting_capital FLOAT      NOT NULL,
    current_cash    FLOAT       NOT NULL,
    is_active       BOOLEAN     DEFAULT true,
    benchmark_ticker VARCHAR(10) DEFAULT 'SPY',
    benchmark_inception_price FLOAT   -- SPY close at inception for relative tracking
);

CREATE TABLE paper_positions (
    id               SERIAL PRIMARY KEY,
    portfolio_id     INTEGER REFERENCES paper_portfolios(id) ON DELETE CASCADE,
    stock_id         INTEGER REFERENCES stocks(id),
    entry_signal_id  INTEGER REFERENCES signals(id),
    opened_at        TIMESTAMPTZ NOT NULL,
    entry_price      FLOAT       NOT NULL,
    shares           FLOAT       NOT NULL,
    stop_loss_price  FLOAT,
    take_profit_price FLOAT,
    UNIQUE(portfolio_id, stock_id)   -- one position per ticker at a time
);

CREATE TABLE paper_trades (
    id               SERIAL PRIMARY KEY,
    portfolio_id     INTEGER REFERENCES paper_portfolios(id) ON DELETE CASCADE,
    stock_id         INTEGER REFERENCES stocks(id),
    entry_signal_id  INTEGER REFERENCES signals(id),
    exit_signal_id   INTEGER REFERENCES signals(id) NULLABLE,
    opened_at        TIMESTAMPTZ NOT NULL,
    closed_at        TIMESTAMPTZ NOT NULL,
    entry_price      FLOAT       NOT NULL,
    exit_price       FLOAT       NOT NULL,
    shares           FLOAT       NOT NULL,
    realized_pnl     FLOAT       NOT NULL,
    return_pct       FLOAT       NOT NULL,
    exit_reason      VARCHAR(30) NOT NULL
        -- signal_reversal | stop_loss | take_profit | max_positions
);

CREATE TABLE paper_portfolio_snapshots (
    id                              SERIAL PRIMARY KEY,
    portfolio_id                    INTEGER REFERENCES paper_portfolios(id) ON DELETE CASCADE,
    snapshot_date                   DATE    NOT NULL,
    total_value                     FLOAT   NOT NULL,
    cash                            FLOAT   NOT NULL,
    equity_value                    FLOAT   NOT NULL,
    open_positions                  INTEGER NOT NULL,
    benchmark_price                 FLOAT,
    daily_return_pct                FLOAT,
    cumulative_return_pct           FLOAT,
    benchmark_cumulative_return_pct FLOAT,
    UNIQUE(portfolio_id, snapshot_date)
);
```

---

### 1.2 Config additions

**File:** `backend/app/config.py`

```python
paper_portfolio_enabled: bool = False
paper_portfolio_starting_capital: float = 100_000.0
paper_portfolio_position_size_pct: float = 0.10   # 10% of portfolio per position
paper_portfolio_max_positions: int = 10
paper_portfolio_max_per_sector: int = 3            # concentration limit
paper_portfolio_stop_loss_pct: float = 0.08        # 8% stop-loss from entry
paper_portfolio_take_profit_pct: float = 0.20      # 20% take-profit from entry
paper_portfolio_min_strength: str = "moderate"     # minimum signal strength to enter
```

---

### 1.3 ORM models

**File:** `backend/app/models/paper_portfolio.py`

Four ORM classes: `PaperPortfolio`, `PaperPosition`, `PaperTrade`, `PaperPortfolioSnapshot`.
Follow the SQLAlchemy 2.0 `Mapped`/`mapped_column` syntax used throughout the project.

---

### 1.4 Celery tasks

#### `update_paper_portfolio` task

**File:** `backend/worker/tasks/signals/paper_portfolio_task.py`

Runs at **:35** (after signal generation at :30, weekdays only).

Algorithm:
1. Load the active `PaperPortfolio` (create one on first run if none exists, using
   `PAPER_PORTFOLIO_STARTING_CAPITAL` and today's SPY close as `benchmark_inception_price`).
2. **Close positions:** For each open `PaperPosition`:
   a. Fetch latest close price from `MarketDataDaily`.
   b. If price dropped `>= stop_loss_pct` from entry → close, `exit_reason = "stop_loss"`.
   c. If price gained `>= take_profit_pct` from entry → close, `exit_reason = "take_profit"`.
   d. Fetch latest signal for this ticker. If direction is not `"bullish"` → close,
      `exit_reason = "signal_reversal"`.
   e. On close: record `PaperTrade`, add `shares * exit_price` back to `current_cash`,
      delete `PaperPosition`.
3. **Open positions:** For each ticker with a new signal where:
   - `direction == "bullish"`
   - `strength` is at least `min_strength` (moderate or strong)
   - No existing open position for this ticker
   - Current position count `< max_positions`
   - Sector position count `< max_per_sector`
   - `current_cash >= position_size_pct * total_portfolio_value` (enough cash)

   Then open: fetch latest close from `MarketDataDaily`, compute
   `shares = floor((portfolio_value * position_size_pct) / close_price)`,
   deduct cost from `current_cash`, insert `PaperPosition` with stop-loss and take-profit
   prices pre-computed.
4. Commit. Log summary: positions opened, closed, P&L.

Gate on `settings.paper_portfolio_enabled`.

#### `snapshot_paper_portfolio` task

**File:** `backend/worker/tasks/signals/paper_portfolio_task.py` (same file, second task)

Runs **daily at 21:30 UTC** (after US market close + 90 min for market data to propagate).
Add this to `beat_schedule.py`.

Algorithm:
1. Load active portfolio + all open positions.
2. Fetch latest close for each open position ticker from `MarketDataDaily`.
3. `equity_value = sum(shares * close_price for each position)`
4. `total_value = current_cash + equity_value`
5. Fetch SPY close for today.
6. `cumulative_return_pct = (total_value - starting_capital) / starting_capital`
7. `benchmark_cumulative_return_pct = (spy_close - benchmark_inception_price) / benchmark_inception_price`
8. Compare to previous snapshot for `daily_return_pct`.
9. Insert `PaperPortfolioSnapshot`. Commit.

---

### 1.5 API endpoints

**File:** `backend/app/api/portfolio.py` (new file, register in `router.py`)

All endpoints require JWT auth. No admin-only restriction — any authenticated user can view.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/portfolio/summary` | Current value, total return %, SPY return %, open positions count, cash %, inception date |
| `GET` | `/api/portfolio/positions` | Open positions: ticker, sector, entry date, entry price, current price, unrealized P&L %, shares |
| `GET` | `/api/portfolio/trades` | Completed trades, paginated (`page`, `per_page`): ticker, entry→exit, return %, exit reason, dates |
| `GET` | `/api/portfolio/performance` | Daily snapshots for equity curve: `[{date, total_value, benchmark_value}]` |
| `GET` | `/api/portfolio/stats` | Sharpe ratio, max drawdown, win rate, avg win %, avg loss %, alpha, beta vs benchmark |

For `stats`, compute from `paper_portfolio_snapshots` + `paper_trades`:
- **Sharpe:** annualized mean daily return / std of daily returns, risk-free = 0
- **Max drawdown:** max peak-to-trough decline in total_value over snapshot history
- **Win rate:** trades with `return_pct > 0` / total closed trades
- **Alpha/Beta:** regression of portfolio daily returns vs SPY daily returns over snapshot history

---

### 1.6 Pydantic schemas

**File:** `backend/app/schemas/portfolio.py` (new file)

`PortfolioSummary`, `PortfolioPosition`, `PortfolioTrade`, `PortfolioSnapshot`,
`PortfolioStats`, `PaginatedTrades`. Use `from_attributes = True`.

---

### 1.7 Frontend — Portfolio page

**File:** `frontend/src/pages/PortfolioPage.tsx` (new page, lazy-loaded)

Register at `/portfolio` in `App.tsx` (protected route).
Add "Portfolio" link to the sidebar below Signals.

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Portfolio Value: $104,231   +4.23% vs SPY +2.11%  │
│  Inception: 2026-08-01   Cash: 38%   Positions: 6  │
└─────────────────────────────────────────────────────┘

[Equity Curve Chart — portfolio line vs SPY line, normalized to 100 at inception]

┌── Open Positions ─────────────────────────────────┐
│ Ticker │ Sector    │ Entry    │ Current │ P&L     │
│ AAPL   │ Technology│ $182.00  │ $191.50 │ +5.22%  │
│ JPM    │ Financials│ $198.00  │ $194.20 │ -1.92%  │
└───────────────────────────────────────────────────┘

┌── Performance Stats ──────────────────────────────┐
│ Sharpe: 1.42  Max DD: -6.8%  Win Rate: 61%       │
│ Alpha: +2.1%  Beta: 0.87     Avg Win: +8.2%      │
└───────────────────────────────────────────────────┘

┌── Trade History ──────────────────────────────────┐
│ (paginated table with exit reason badges)         │
└───────────────────────────────────────────────────┘
```

Reuse `EquityCurveChart` from the backtesting frontend with a benchmark overlay.
Exit reason badges: `signal_reversal` (blue), `stop_loss` (red), `take_profit` (green),
`max_positions` (gray).

---

## Part 2 — Smarter Feedback Loop (Milestone 22b)

### 2.1 Return-weighted accuracy in weight optimizer

**File:** `backend/worker/tasks/signals/weight_optimizer.py`

**Current behavior:** Each signal is scored binary (correct/wrong) when computing component
accuracy. All signals get equal vote.

**New behavior:** Weight each signal's vote by `abs(price_change_pct)` from `SignalOutcome`.
A component that was correct on a 5% move contributes 5× more than one correct on a 0.1% move.

```python
# Before
component_correct["sentiment_momentum"] += 1
component_total["sentiment_momentum"] += 1

# After
magnitude = abs(float(row.price_change_pct))
vote = magnitude if sign_matches else 0.0
component_correct["sentiment_momentum"] += vote
component_total["sentiment_momentum"] += magnitude
```

No schema changes. The `price_change_pct` column already exists on `SignalOutcome`.

---

### 2.2 Add `analyst_score` to weight optimizer

**File:** `backend/worker/tasks/signals/weight_optimizer.py`

The `analyst_score` column exists on `Signal` (added in Phase 21g) but is not yet tracked
in the component accuracy loop.

- Add `Signal.analyst_score` to the query `select()` call.
- Add `"analyst"` to the `components` list.
- Add the tracking block for `analyst_score` (same pattern as `earnings_score`):
  skip rows where `analyst_score is None` or `abs(analyst_score) <= 0.01`.
- Add `"analyst": round(clamped.get("analyst", 0.07), 4)` to `result_weights`.
- Add `"analyst": weights.get("analyst", 0.07)` in `_upsert_weights()` and include
  `analyst` in the `SignalWeight` ORM column (migration needed if not present).

Check whether `signal_weights` table has an `analyst` column; if not, add it in the
same migration 015 or a separate 016.

---

### 2.3 Regime-conditional weights

**DB (add to migration 015 or new 016):**

```sql
CREATE TABLE regime_adaptive_weights (
    id           SERIAL PRIMARY KEY,
    sector_id    INTEGER REFERENCES sectors(id) NULLABLE,
    regime       VARCHAR(20) NOT NULL,
    sentiment_momentum FLOAT NOT NULL,
    sentiment_volume   FLOAT NOT NULL,
    price_momentum     FLOAT NOT NULL,
    volume_anomaly     FLOAT NOT NULL,
    earnings           FLOAT NOT NULL DEFAULT 0.10,
    options            FLOAT NOT NULL DEFAULT 0.08,
    analyst            FLOAT NOT NULL DEFAULT 0.07,
    rsi                FLOAT NOT NULL DEFAULT 0.0,
    trend              FLOAT NOT NULL DEFAULT 0.0,
    sample_count       INTEGER NOT NULL,
    accuracy_pct       FLOAT   NOT NULL,
    computed_at        TIMESTAMPTZ NOT NULL,
    UNIQUE(sector_id, regime)
);
```

**File:** `backend/worker/tasks/signals/weight_optimizer.py`

After the existing per-sector weight computation, add `_compute_regime_weights()`:

For each `(sector_id, regime)` combination (6 sectors × 5 regimes + global = 35 pairs):
- Filter signals to only those with `market_regime == regime`
- If `sample_count >= settings.feedback_min_samples` (reuse existing threshold):
  run the same component accuracy computation as the sector optimizer
- Upsert into `regime_adaptive_weights`

**File:** `backend/worker/utils/signal_formula.py`

Extend `resolve_weights()` to accept `market_regime: str | None = None`:

```python
def resolve_weights(
    weights_map: dict | None,
    sector_id: int | None,
    has_earnings: bool = False,
    has_options: bool | None = None,
    has_analyst: bool = False,
    market_regime: str | None = None,
    regime_weights_map: dict | None = None,  # keyed by (sector_id, regime)
) -> dict:
```

Lookup priority:
1. `regime_weights_map[(sector_id, market_regime)]` — most specific
2. `regime_weights_map[(None, market_regime)]` — global regime fallback
3. `weights_map[sector_id]` — sector weights (existing)
4. `weights_map[None]` — global weights (existing)
5. `default_weights(...)` — hardcoded defaults

The signal generator loads both `weights_map` and `regime_weights_map` at the start of
each generation run (similar to how `weights_map` is loaded today), then passes
`market_regime` from the current signal's computed regime into `resolve_weights()`.

**Cold start:** regime weights will be absent for combinations with fewer than
`feedback_min_samples` signals — the fallback chain handles this transparently.

---

### 2.4 Beat schedule update

**File:** `backend/worker/beat_schedule.py`

Add two new schedule entries:

```python
# Paper portfolio update (after signal generation)
"update-paper-portfolio": {
    "task": "worker.tasks.signals.paper_portfolio_task.update_paper_portfolio",
    "schedule": crontab(minute=35),   # weekdays handled inside the task
    "options": {"queue": "signals"},
},
# Daily portfolio snapshot (after US market close)
"snapshot-paper-portfolio": {
    "task": "worker.tasks.signals.paper_portfolio_task.snapshot_paper_portfolio",
    "schedule": crontab(hour=21, minute=30),
    "options": {"queue": "signals"},
},
```

---

## Update CLAUDE.md

**Beat schedule section** — add:
```
:35 → update paper portfolio (close/open positions from latest signals, if PAPER_PORTFOLIO_ENABLED)
21:30 → snapshot paper portfolio (daily equity curve + benchmark tracking)
```

**What's implemented** — add paper portfolio bullet covering: 4 new DB tables, position
management (stop-loss/take-profit/signal-reversal exits, sector concentration limit),
daily equity snapshots, SPY benchmark tracking, Portfolio page with equity curve + positions
+ trades + Sharpe/drawdown/alpha/beta stats.

**Signal scoring** — add note: weight optimizer now uses return-weighted accuracy (magnitude
of `price_change_pct` as vote weight), regime-conditional weights per (sector, regime) pair,
and tracks `analyst_score` component accuracy.

---

## Tests

### Paper portfolio
- `update_paper_portfolio`: mock signals + market data → assert position opened when conditions met
- `update_paper_portfolio`: stop-loss triggers correctly (price < entry * (1 - stop_loss_pct))
- `update_paper_portfolio`: take-profit triggers correctly
- `update_paper_portfolio`: signal reversal closes position, records trade
- `update_paper_portfolio`: max_positions limit respected (no new position when at capacity)
- `update_paper_portfolio`: sector concentration limit respected (max 3 per sector)
- `snapshot_paper_portfolio`: total_value = cash + equity, cumulative_return computed correctly
- Portfolio stats: Sharpe, max drawdown, win rate computed correctly from fixture trades

### Feedback loop
- Return-weighted accuracy: large-magnitude correct signals outweigh small-magnitude ones
- Regime weight optimizer: only runs when sample_count >= feedback_min_samples for that regime
- `resolve_weights()`: regime-specific weights used when available, falls back to sector → global
- `analyst_score` appears in `result_weights` dict from `_compute_sector_weights()`

---

## Deployment

Migration required on Docker VM.

```bash
# Docker VM
cd ~/market-tracker
git pull
docker compose run --rm backend alembic upgrade head
docker compose up -d backend

# Compute VM
cd /opt/stock-predictor
git pull
sudo systemctl restart celery-worker celery-beat
```

Add to `.env` on Docker VM (both are opt-in):
```
PAPER_PORTFOLIO_ENABLED=true
```

The portfolio creates itself on the first `:35` run after the env var is set.
Regime weights will start populating on the next 4 AM weight optimizer run.
