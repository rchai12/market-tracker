# Phase 21c: Signal Formula Refactor — Implementation Specification

## Overview

RSI and technical trend indicators are **lagging** — by the time SMA20 crosses above SMA50 or MACD
diverges, the move has already happened. Using them as direct additive components of the composite
score is counterproductive: they correlate weakly with future direction and dilute the signal's
sensitivity to the components that actually carry predictive information (sentiment, price
momentum, earnings surprise).

This phase:
1. **Removes RSI and trend from the composite score formula** — weights set to 0.0
2. **Introduces a market regime classifier** — uses RSI and trend as *context* about market
   conditions, applies a multiplier to boost confidence when the signal is trend-confirmed
   or dampen it when the stock is technically extended
3. **Rebalances weights** — 25% freed from RSI/trend redistributed to the remaining predictive components
4. **Stores `market_regime`** on each Signal for UI display and future analysis
5. **Updates the weight optimizer** — removes RSI/trend, adds earnings (from Phase 21b) to adaptive
   optimization; adds `earnings` column to `signal_weights` table
6. **Updates the frontend** — ComponentBreakdown distinguishes predictive vs regime-context bars;
   SignalCard shows a regime badge

> **Dependency:** Phase 21b must be merged first. This spec assumes `earnings_score` exists on
> the Signal model and `EarningsEstimate` table exists.

---

## Files To Read Before Implementing

- `backend/worker/tasks/signals/signal_generator.py` — weight constants, `_compute_composite_score`, `_default_weights`
- `backend/worker/tasks/signals/component_scores.py` — existing scoring functions
- `backend/worker/tasks/signals/weight_optimizer.py` — component list, upsert logic
- `backend/app/models/signal.py` — add `market_regime` column
- `backend/app/models/signal_weight.py` — add `earnings` column
- `backend/app/schemas/signal.py` — `SignalResponse`, `SignalWeightsResponse`
- `backend/alembic/versions/009_earnings_surprise.py` — match migration style, use `down_revision = "009"`
- `frontend/src/types/signal.ts` — Signal and SignalWeights interfaces
- `frontend/src/components/Signals/ComponentBreakdown.tsx` — UI to update
- `frontend/src/components/Signals/SignalCard.tsx` — add regime badge

---

## Step 1: Database Migration `010_formula_refactor`

File: `backend/alembic/versions/010_formula_refactor.py`

```
revision = "010"
down_revision = "009"
```

### Upgrade

```python
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    # Add market_regime label to signals
    op.add_column(
        "signals",
        sa.Column("market_regime", sa.String(20), nullable=True),
    )

    # Add earnings weight column to signal_weights
    op.add_column(
        "signal_weights",
        sa.Column("earnings", sa.Numeric(5, 4), nullable=False, server_default="0.1"),
    )
```

### Downgrade

```python
def downgrade() -> None:
    op.drop_column("signal_weights", "earnings")
    op.drop_column("signals", "market_regime")
```

---

## Step 2: Update `backend/app/models/signal.py`

Add after `retail_sentiment_score`:

```python
market_regime: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

---

## Step 3: Update `backend/app/models/signal_weight.py`

Add after `options`:

```python
earnings: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.10)
```

---

## Step 4: Update `backend/worker/tasks/signals/signal_generator.py`

### 4a. Replace weight constants

Remove the existing weight constants and replace with:

```python
# ── Base weights (4 predictive components; RSI and trend are regime-only) ──
WEIGHT_SENTIMENT_MOMENTUM = 0.40
WEIGHT_SENTIMENT_VOLUME   = 0.25
WEIGHT_PRICE_MOMENTUM     = 0.20
WEIGHT_VOLUME_ANOMALY     = 0.15

# With options only (8% added; scale other 4 down proportionally)
WEIGHT_SENTIMENT_MOMENTUM_OPT = 0.37
WEIGHT_SENTIMENT_VOLUME_OPT   = 0.23
WEIGHT_PRICE_MOMENTUM_OPT     = 0.18
WEIGHT_VOLUME_ANOMALY_OPT     = 0.14
WEIGHT_OPTIONS                = 0.08

# With earnings only (10% added; scale other 4 down proportionally)
WEIGHT_SENTIMENT_MOMENTUM_EARN = 0.36
WEIGHT_SENTIMENT_VOLUME_EARN   = 0.22
WEIGHT_PRICE_MOMENTUM_EARN     = 0.18
WEIGHT_VOLUME_ANOMALY_EARN     = 0.14
WEIGHT_EARNINGS                = 0.10

# With both earnings (10%) + options (8%)
WEIGHT_SENTIMENT_MOMENTUM_BOTH = 0.33
WEIGHT_SENTIMENT_VOLUME_BOTH   = 0.21
WEIGHT_PRICE_MOMENTUM_BOTH     = 0.16
WEIGHT_VOLUME_ANOMALY_BOTH     = 0.12
# WEIGHT_EARNINGS = 0.10  (same)
# WEIGHT_OPTIONS  = 0.08  (same)
```

### 4b. Add `apply_regime_multiplier` pure function

Add after the weight constants:

```python
def apply_regime_multiplier(
    composite: float,
    rsi_score: float | None,
    trend_score: float | None,
) -> tuple[float, str]:
    """Apply a regime-based confidence multiplier to the composite score.

    RSI and trend are no longer additive components — instead they provide
    context about market conditions and adjust how much we trust the signal.

    RSI score is tanh-scaled: positive → oversold, negative → overbought.
    Threshold |0.4| ≈ raw RSI of 35/65 (moderately extended).

    Trend score > 0.3 indicates a meaningful uptrend (SMA20 > SMA50 + positive MACD).
    Trend score < -0.3 indicates a meaningful downtrend.

    Priority order:
    1. RSI extreme (|rsi_score| > 0.4): dampen 15% regardless of trend.
       Stock is technically stretched in either direction — lower confidence.
    2. Strong trend confirming signal: boost 15%.
       The market structure agrees with our signal direction.
    3. Strong trend opposing signal: dampen 15%.
       The market structure fights our signal — be cautious.
    4. Sideways / neutral: no change.

    Returns (adjusted_composite, regime_label).
    regime_label: "overbought" | "oversold" | "trending_up" | "trending_down" | "sideways"
    """
    rsi_val   = rsi_score   if rsi_score   is not None else 0.0
    trend_val = trend_score if trend_score is not None else 0.0

    # Priority 1: technically extended RSI
    if abs(rsi_val) > 0.4:
        regime = "overbought" if rsi_val < 0 else "oversold"
        return composite * 0.85, regime

    # Priority 2 & 3: meaningful trend
    if abs(trend_val) > 0.3:
        composite_bullish = composite > 0
        trend_bullish = trend_val > 0
        regime = "trending_up" if trend_bullish else "trending_down"
        if composite_bullish == trend_bullish:
            return composite * 1.15, regime   # trend confirms signal
        else:
            return composite * 0.85, regime   # trend opposes signal

    return composite, "sideways"
```

### 4c. Replace `_default_weights`

```python
def _default_weights(has_options: bool = False, has_earnings: bool = False) -> dict:
    """Return default weights for 4-component base formula.

    RSI and trend are set to 0.0 — they are no longer additive signal components.
    They are used only for regime classification via apply_regime_multiplier.
    """
    if has_options and has_earnings:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_BOTH,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME_BOTH,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM_BOTH,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY_BOTH,
            "rsi":                0.0,
            "trend":              0.0,
            "earnings":           WEIGHT_EARNINGS,
            "options":            WEIGHT_OPTIONS,
            "source":             "default",
        }
    elif has_options:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_OPT,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME_OPT,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM_OPT,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY_OPT,
            "rsi":                0.0,
            "trend":              0.0,
            "earnings":           0.0,
            "options":            WEIGHT_OPTIONS,
            "source":             "default",
        }
    elif has_earnings:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_EARN,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME_EARN,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM_EARN,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY_EARN,
            "rsi":                0.0,
            "trend":              0.0,
            "earnings":           WEIGHT_EARNINGS,
            "options":            0.0,
            "source":             "default",
        }
    else:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM,
            "sentiment_volume":   WEIGHT_SENTIMENT_VOLUME,
            "price_momentum":     WEIGHT_PRICE_MOMENTUM,
            "volume_anomaly":     WEIGHT_VOLUME_ANOMALY,
            "rsi":                0.0,
            "trend":              0.0,
            "earnings":           0.0,
            "options":            0.0,
            "source":             "default",
        }
```

### 4d. Replace `_get_weights`

```python
def _get_weights(
    weights_map: dict | None,
    sector_id: int | None,
    has_earnings: bool = False,
) -> dict:
    """Look up adaptive weights: sector-specific -> global -> defaults.

    Adaptive weights (from SignalWeight table) contain rsi and trend columns
    which will now always be 0.0 after the weight optimizer is updated.
    The earnings key is added to SignalWeight in this phase.
    """
    if weights_map:
        if sector_id is not None and sector_id in weights_map:
            return weights_map[sector_id]
        if None in weights_map:
            return weights_map[None]
    return _default_weights(
        has_options=settings.options_flow_enabled,
        has_earnings=has_earnings,
    )
```

### 4e. Replace `_compute_composite_score`

```python
async def _compute_composite_score(
    session: AsyncSession,
    stock_id: int,
    now: datetime,
    weights_map: dict | None = None,
    sector_id: int | None = None,
) -> dict | None:
    """Compute all components and the weighted composite for a stock.

    RSI and trend are computed for regime classification and storage,
    but their weights in the composite are 0.0.
    apply_regime_multiplier adjusts the raw composite based on market conditions.
    """
    sent_momentum = await calc_sentiment_momentum(session, stock_id, now)
    sent_volume   = await calc_sentiment_volume(session, stock_id, now)
    price_mom     = await calc_price_momentum(session, stock_id, now)
    vol_anomaly   = await calc_volume_anomaly(session, stock_id, now)
    rsi           = await calc_rsi_score(session, stock_id, now)
    trend         = await calc_trend_score(session, stock_id, now)
    options       = await calc_options_score(session, stock_id, now)
    earnings      = await calc_earnings_surprise_score(session, stock_id, now)

    article_count = await get_recent_article_count(session, stock_id, now)

    has_sentiment = sent_momentum is not None
    has_market    = price_mom is not None

    if not has_sentiment and not has_market:
        return None

    sm        = sent_momentum if sent_momentum is not None else 0.0
    sv        = sent_volume   if sent_volume   is not None else 0.0
    pm        = price_mom     if price_mom     is not None else 0.0
    va        = vol_anomaly   if vol_anomaly   is not None else 0.0
    rsi_val   = rsi           if rsi           is not None else 0.0
    trend_val = trend         if trend         is not None else 0.0
    opts_val  = options       if options       is not None else 0.0
    earn_val  = earnings      if earnings      is not None else 0.0

    has_earnings = earnings is not None
    w = _get_weights(weights_map, sector_id, has_earnings=has_earnings)

    # Raw composite: 4 predictive components (+ earnings/options when active)
    # RSI and trend weights are 0.0 — they do not contribute here
    raw_composite = (
        w["sentiment_momentum"] * sm
        + w["sentiment_volume"]   * sv
        + w["price_momentum"]     * pm
        + w["volume_anomaly"]     * va
        + w.get("earnings", 0.0)  * earn_val
        + w.get("options", 0.0)   * opts_val
    )

    # Regime classification: RSI and trend as context, not signal components
    composite, market_regime = apply_regime_multiplier(raw_composite, rsi_val, trend_val)

    return {
        "composite":          composite,
        "sentiment_momentum": sm,
        "sentiment_volume":   sv,
        "price_momentum":     pm,
        "volume_anomaly":     va,
        "rsi_score":          rsi_val,
        "trend_score":        trend_val,
        "options_score":      opts_val,
        "earnings_score":     earn_val,
        "market_regime":      market_regime,
        "article_count":      article_count,
        "weights_source":     w["source"],
    }
```

### 4f. Store `market_regime` on Signal object

In `_generate_signals_async`, in the `Signal(...)` constructor, add:

```python
earnings_score=round(score_data["earnings_score"], 5) if score_data.get("earnings_score") else None,
market_regime=score_data.get("market_regime"),
```

### 4g. Update `_load_all_weights`

Add `earnings` and force `rsi`/`trend` to 0.0 when reading from DB:

```python
async def _load_all_weights(session: AsyncSession) -> dict:
    """Pre-load all adaptive weights into a sector_id -> weights dict."""
    if not settings.feedback_enabled:
        return {}

    result = await session.execute(
        select(SignalWeight).where(SignalWeight.sample_count >= settings.feedback_min_samples)
    )
    rows = result.scalars().all()

    weights_map = {}
    for row in rows:
        w = {
            "sentiment_momentum": float(row.sentiment_momentum),
            "sentiment_volume":   float(row.sentiment_volume),
            "price_momentum":     float(row.price_momentum),
            "volume_anomaly":     float(row.volume_anomaly),
            "rsi":                0.0,   # regime only — zero weight in composite
            "trend":              0.0,   # regime only — zero weight in composite
            "earnings":           float(row.earnings),
            "options":            float(row.options),
            "source":             "sector" if row.sector_id else "global",
        }
        weights_map[row.sector_id] = w
    return weights_map
```

### 4h. Update `_build_reasoning`

Remove the RSI and trend direction clauses. Replace them with a regime clause:

```python
def _build_reasoning(
    ticker: str, score_data: dict, direction: str, strength: str
) -> str:
    """Generate human-readable reasoning string for the signal."""
    parts = [f"{ticker}: {strength} {direction} signal (score: {score_data['composite']:.3f})"]

    sm = score_data["sentiment_momentum"]
    sv = score_data["sentiment_volume"]
    pm = score_data["price_momentum"]
    va = score_data["volume_anomaly"]

    if abs(sm) > 0.3:
        sent_dir = "positive" if sm > 0 else "negative"
        parts.append(f"Sentiment momentum is {sent_dir} ({sm:.3f})")

    if score_data["article_count"] > 0:
        parts.append(f"{score_data['article_count']} articles in last 24h")

    if abs(pm) > 0.2:
        price_dir = "upward" if pm > 0 else "downward"
        parts.append(f"Price momentum is {price_dir} ({pm:.3f})")

    if abs(va) > 0.3:
        vol_desc = "above" if va > 0 else "below"
        parts.append(f"Volume {vol_desc} average ({va:.3f})")

    earn_val = score_data.get("earnings_score", 0)
    if earn_val and abs(earn_val) > 0.2:
        earn_dir = "beat" if earn_val > 0 else "miss"
        parts.append(f"Recent earnings {earn_dir} (score: {earn_val:.3f})")

    opts_val = score_data.get("options_score", 0)
    if abs(opts_val) > 0.3:
        opts_desc = "bullish" if opts_val > 0 else "bearish"
        parts.append(f"Options flow is {opts_desc} ({opts_val:.3f})")

    regime = score_data.get("market_regime", "sideways")
    if regime not in ("sideways", None):
        regime_display = regime.replace("_", " ")
        parts.append(f"Market regime: {regime_display}")

    return ". ".join(parts) + "."
```

---

## Step 5: Update `backend/worker/tasks/signals/weight_optimizer.py`

### 5a. Update `_compute_sector_weights`

Change the `components` list and the per-row processing to exclude RSI and trend,
and include earnings. Remove the RSI, trend, and options score blocks.

Replace the `components` definition and the loop body:

```python
# Component list: RSI and trend excluded (regime only); earnings added from Phase 21b
components = ["sentiment_momentum", "sentiment_volume", "price_momentum", "volume_anomaly", "earnings"]
if settings.options_flow_enabled:
    components.append("options")
```

In the query, add `Signal.earnings_score`:

```python
query = (
    select(
        Signal.sentiment_score,
        Signal.price_score,
        Signal.volume_score,
        Signal.options_score,
        Signal.earnings_score,    # new
        Signal.direction,
        SignalOutcome.is_correct,
        SignalOutcome.price_change_pct,
    )
    ...
)
```

In the per-row loop, remove the RSI and trend blocks and add earnings:

```python
for row in rows:
    actual_dir = 1.0 if float(row.price_change_pct) > 0 else -1.0

    # Sentiment momentum (stored as sentiment_score)
    if row.sentiment_score is not None:
        if (1.0 if float(row.sentiment_score) > 0 else -1.0) == actual_dir:
            component_correct["sentiment_momentum"] += 1
        component_total["sentiment_momentum"] += 1

    # Price momentum
    if row.price_score is not None:
        if (1.0 if float(row.price_score) > 0 else -1.0) == actual_dir:
            component_correct["price_momentum"] += 1
        component_total["price_momentum"] += 1

    # Volume anomaly
    if row.volume_score is not None:
        if (1.0 if float(row.volume_score) > 0 else -1.0) == actual_dir:
            component_correct["volume_anomaly"] += 1
        component_total["volume_anomaly"] += 1

    # Earnings surprise
    if row.earnings_score is not None and abs(float(row.earnings_score)) > 0.01:
        if (1.0 if float(row.earnings_score) > 0 else -1.0) == actual_dir:
            component_correct["earnings"] += 1
        component_total["earnings"] += 1

    # Options score
    if settings.options_flow_enabled and row.options_score is not None:
        if (1.0 if float(row.options_score) > 0 else -1.0) == actual_dir:
            component_correct["options"] += 1
        component_total["options"] += 1

    # Sentiment volume — use overall correctness as proxy (not stored directionally)
    component_correct["sentiment_volume"] += 1 if row.is_correct else 0
    component_total["sentiment_volume"] += 1

    if row.is_correct:
        total_correct += 1
```

### 5b. Update `result_weights` dict in `_compute_sector_weights`

Remove `rsi` and `trend` keys; add `earnings`:

```python
result_weights = {
    "sentiment_momentum": round(clamped["sentiment_momentum"], 4),
    "sentiment_volume":   round(clamped["sentiment_volume"], 4),
    "price_momentum":     round(clamped["price_momentum"], 4),
    "volume_anomaly":     round(clamped["volume_anomaly"], 4),
    "sample_count":       len(rows),
    "accuracy_pct":       round(overall_accuracy, 2),
    "earnings":           round(clamped.get("earnings", WEIGHT_EARNINGS), 4),
}
if settings.options_flow_enabled:
    result_weights["options"] = round(clamped.get("options", 0.08), 4)
return result_weights
```

### 5c. Update `_upsert_weights`

Replace the values dict to use new fields and always write 0.0 for rsi/trend:

```python
async def _upsert_weights(session: AsyncSession, sector_id: int | None, weights: dict) -> None:
    """Insert or update weights for a sector."""
    values = {
        "sector_id":          sector_id,
        "sentiment_momentum": weights["sentiment_momentum"],
        "sentiment_volume":   weights["sentiment_volume"],
        "price_momentum":     weights["price_momentum"],
        "volume_anomaly":     weights["volume_anomaly"],
        "rsi":                0.0,   # regime only; always zero
        "trend":              0.0,   # regime only; always zero
        "earnings":           weights.get("earnings", 0.10),
        "options":            weights.get("options", 0.08),
        "sample_count":       weights["sample_count"],
        "accuracy_pct":       weights["accuracy_pct"],
        "computed_at":        datetime.now(timezone.utc),
    }
    stmt = pg_insert(SignalWeight).values(**values)
    update_set = {k: getattr(stmt.excluded, k) for k in values if k != "sector_id"}
    stmt = stmt.on_conflict_on_constraint("signal_weights_sector_id_key").do_update(set_=update_set)
    await session.execute(stmt)
```

> **Note:** The `WEIGHT_EARNINGS` constant from `signal_generator.py` is not importable here
> (circular import risk). Use the literal `0.10` as the fallback default for earnings in `_upsert_weights`.

---

## Step 6: Update `backend/app/schemas/signal.py`

### 6a. Add `market_regime` to `SignalResponse`

```python
market_regime: str | None = None
earnings_score: float | None = None
```

### 6b. Update `SignalWeightsResponse`

Add `earnings`; keep `rsi` and `trend` (they'll be 0.0 from DB, displayed as regime-only):

```python
class SignalWeightsResponse(BaseModel):
    sector_name: str | None
    sentiment_momentum: float
    sentiment_volume: float
    price_momentum: float
    volume_anomaly: float
    rsi: float          # Always 0.0 post-21c — regime only
    trend: float        # Always 0.0 post-21c — regime only
    earnings: float
    options: float
    sample_count: int
    accuracy_pct: float | None
    computed_at: datetime | None
    source: str
```

---

## Step 7: Update `backend/app/api/signals.py`

In the weights endpoint, the `SignalWeight` rows already have `rsi` and `trend` columns
(now always 0.0 in DB). The `earnings` column is new. Update the mapping to include it:

Find where `SignalWeightsResponse` objects are constructed from `SignalWeight` rows and add:

```python
earnings=float(row.earnings) if row.earnings is not None else 0.10,
```

If the endpoint constructs `SignalWeightsResponse` objects by mapping DB columns,
check whether it uses `model_validate` or manual construction. Add `earnings` accordingly.

---

## Step 8: Frontend — `frontend/src/types/signal.ts`

Add to the `Signal` interface:

```typescript
earnings_score: number | null;
market_regime: string | null;
```

Add to the `SignalWeights` interface:

```typescript
earnings: number;
```

Remove nothing — `rsi` and `trend` remain in `SignalWeights` (they'll be 0.0).

---

## Step 9: Frontend — `frontend/src/components/Signals/ComponentBreakdown.tsx`

Split the component list into two arrays: predictive components and regime context:

```typescript
const PREDICTIVE_COMPONENTS = [
  { key: "sentiment_score",        label: "Sentiment" },
  { key: "sentiment_volume_score", label: "Sent. Volume" },
  { key: "price_score",            label: "Price" },
  { key: "volume_score",           label: "Volume" },
  { key: "earnings_score",         label: "Earnings" },
  { key: "options_score",          label: "Options" },
] as const;

const REGIME_COMPONENTS = [
  { key: "rsi_score",   label: "RSI" },
  { key: "trend_score", label: "Trend" },
] as const;
```

Render them in two sections separated by a label:

```tsx
<div className="space-y-1.5 pt-3 border-t border-gray-200 dark:border-gray-700">
  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
    Signal Components
  </p>
  {PREDICTIVE_COMPONENTS.map(({ key, label }) => {
    const value = signal[key as keyof Signal] as number | null;
    if (value == null) return null;
    return <ComponentBar key={key} label={label} value={value} />;
  })}

  {/* Regime context — informational only, not weighted in composite */}
  {(signal.rsi_score != null || signal.trend_score != null) && (
    <>
      <p className="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mt-3 mb-1">
        Regime Context
      </p>
      {REGIME_COMPONENTS.map(({ key, label }) => {
        const value = signal[key as keyof Signal] as number | null;
        if (value == null) return null;
        return <ComponentBar key={key} label={label} value={value} muted />;
      })}
    </>
  )}

  {/* ML Ensemble section — unchanged */}
  ...
</div>
```

Extract the bar rendering into a local `ComponentBar` component:

```tsx
function ComponentBar({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: number;
  muted?: boolean;
}) {
  const pct = Math.abs(value) * 100;
  const isPositive = value >= 0;
  const barColor = muted
    ? "bg-gray-400 dark:bg-gray-500"
    : isPositive
    ? "bg-emerald-500 dark:bg-emerald-400"
    : "bg-red-500 dark:bg-red-400";

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`w-20 shrink-0 ${muted ? "text-gray-400 dark:text-gray-500" : "text-gray-600 dark:text-gray-400"}`}>
        {label}
      </span>
      <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-700 rounded-full relative overflow-hidden">
        <div className="absolute inset-0 flex items-center">
          <div className="w-1/2" />
          <div className="w-px h-full bg-gray-300 dark:bg-gray-600" />
          <div className="w-1/2" />
        </div>
        {isPositive ? (
          <div
            className={`absolute top-0 h-full rounded-r-full ${barColor}`}
            style={{ left: "50%", width: `${Math.min(pct, 100) / 2}%` }}
          />
        ) : (
          <div
            className={`absolute top-0 h-full rounded-l-full ${barColor}`}
            style={{ right: "50%", width: `${Math.min(pct, 100) / 2}%` }}
          />
        )}
      </div>
      <span
        className={`w-12 text-right font-mono ${
          muted
            ? "text-gray-400 dark:text-gray-500"
            : isPositive
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-red-600 dark:text-red-400"
        }`}
      >
        {value > 0 ? "+" : ""}{value.toFixed(3)}
      </span>
    </div>
  );
}
```

---

## Step 10: Frontend — `frontend/src/components/Signals/SignalCard.tsx`

Add a market regime badge between the direction badge and the article count grid.
Place it in the header row or as a small indicator below it:

```tsx
{/* Regime badge — shown when regime is not sideways */}
{signal.market_regime && signal.market_regime !== "sideways" && (
  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
    signal.market_regime === "trending_up"
      ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
      : signal.market_regime === "trending_down"
      ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"
      : "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400"
  }`}>
    {signal.market_regime.replace("_", " ")}
  </span>
)}
```

Place this inside the `<Link>` block, in the first `flex items-center justify-between` row
(the row with ticker name and direction badge), or as its own row below the direction badge.
Keep it visually compact — it's secondary information.

---

## Step 11: Frontend — `frontend/src/components/Signals/WeightsTable.tsx` (if exists)

If a `WeightsTable` component exists, update it to:
1. Show `earnings` weight column
2. Label `rsi` and `trend` columns as "Regime" (gray text, 0.0 values)

---

## Test Requirements

### New file: `backend/tests/test_formula_refactor.py`

**Tests for `apply_regime_multiplier`:**

| Test case | Input | Expected output |
|---|---|---|
| RSI score +0.5 (oversold, rsi_val > 0.4) | composite=0.4 | (0.34, "oversold") |
| RSI score -0.5 (overbought, rsi_val < -0.4) | composite=0.4 | (0.34, "overbought") |
| RSI score -0.5, bearish composite | composite=-0.4 | (-0.34, "overbought") |
| trend_val=+0.5, composite=+0.4 (trend confirms bullish) | — | (0.46, "trending_up") |
| trend_val=+0.5, composite=-0.4 (trend opposes bearish) | — | (-0.34, "trending_up") |
| trend_val=-0.5, composite=-0.4 (trend confirms bearish) | — | (-0.46, "trending_down") |
| trend_val=-0.5, composite=+0.4 (trend opposes bullish) | — | (0.34, "trending_down") |
| RSI 0.5 + trend 0.5 (RSI wins priority 1) | composite=0.4 | (0.34, "oversold") |
| Both RSI and trend None | composite=0.4 | (0.4, "sideways") |
| Weak trend (|trend_val| < 0.3), neutral RSI | composite=0.4 | (0.4, "sideways") |
| Zero composite | composite=0.0 | (0.0, "sideways") |

**Tests for `_default_weights`:**

| Test case | Assertion |
|---|---|
| No options, no earnings | rsi=0.0, trend=0.0, sm+sv+pm+va = 1.0 |
| has_earnings=True | earnings=0.10, rsi=0.0, trend=0.0, sum = 1.0 |
| has_options=True | options=0.08, earnings=0.0, rsi=0.0, sum = 1.0 |
| Both options and earnings | options=0.08, earnings=0.10, rsi=0.0, sum = 1.0 |

Verify that each weight set sums exactly to 1.0 (floating-point tolerance 1e-9).

**Tests for weight optimizer changes:**

| Test case | Assertion |
|---|---|
| `_compute_sector_weights` — RSI and trend not in component list | no rsi/trend in result dict |
| Earnings score available → included in accuracy computation | earnings key in result |
| Earnings score None → excluded from total (not penalized) | total count unchanged |
| `_upsert_weights` — always writes rsi=0.0, trend=0.0 | DB values are 0.0 |

**Integration: `_compute_composite_score` (mock DB functions):**

| Test case | Assertion |
|---|---|
| rsi_score computed, trend_score computed → regime applied | market_regime is set, not "unknown" |
| rsi_score > 0.4, composite > 0 → dampened 15% | composite ≈ raw * 0.85 |
| trend confirms direction → boosted 15% | composite ≈ raw * 1.15 |
| RSI None, trend None → regime "sideways", no multiplier | composite = raw |

---

## Implementation Order

1. Write migration `010_formula_refactor` — run `make migrate`
2. Update `backend/app/models/signal.py` — add `market_regime`
3. Update `backend/app/models/signal_weight.py` — add `earnings`
4. Add `apply_regime_multiplier` to `signal_generator.py`
5. Replace weight constants in `signal_generator.py`
6. Replace `_default_weights`, `_get_weights`, `_compute_composite_score`, `_build_reasoning`
7. Update `_load_all_weights` to zero-out RSI/trend, include earnings
8. Update `_generate_signals_async` Signal constructor — add `market_regime`, `earnings_score`
9. Write unit tests for `apply_regime_multiplier` and `_default_weights` — all must pass
10. Update `weight_optimizer.py` — components list, loop, result dict, upsert
11. Update `backend/app/schemas/signal.py` — add `market_regime`, `earnings_score`, `earnings` weight
12. Update `backend/app/api/signals.py` — include `earnings` in weights response
13. Run `make test-unit` — all must pass before touching frontend
14. Update `frontend/src/types/signal.ts` — add `earnings_score`, `market_regime`, `earnings`
15. Update `frontend/src/components/Signals/ComponentBreakdown.tsx`
16. Update `frontend/src/components/Signals/SignalCard.tsx` — add regime badge
17. Update `WeightsTable` component if it exists
18. Run all unit tests + frontend build

---

## Post-Deploy Steps

```bash
# Docker VM
make migrate      # applies 010_formula_refactor
make build
make up

# Compute VM
git pull origin main
sudo systemctl restart celery-worker celery-beat
```

After deploy:
1. Trigger signal generation from Admin page (or wait for next :30 run)
2. Check a recent signal — verify `market_regime` is populated
3. Check a signal for a stock with strong trend — verify composite is visibly affected
4. Check `GET /api/signals/weights` — verify `earnings` field present, `rsi` and `trend` = 0.0
5. After next 4 AM weight optimizer run, verify new DB weights have `rsi=0.0`, `trend=0.0`, `earnings` > 0

---

## Post-Deploy Validation Checklist

- [ ] `signals.market_regime` column exists and is populated after next signal generation
- [ ] `signal_weights.earnings` column exists
- [ ] `GET /api/signals` response includes `market_regime` and `earnings_score`
- [ ] `GET /api/signals/weights` response includes `earnings`; `rsi` and `trend` are 0.0
- [ ] ComponentBreakdown UI shows "Signal Components" and "Regime Context" sections
- [ ] SignalCard shows regime badge for non-sideways regimes
- [ ] Composite scores are visually different for trending vs sideways stocks
- [ ] `make test-unit` passes
