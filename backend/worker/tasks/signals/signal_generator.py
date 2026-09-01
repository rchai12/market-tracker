"""Signal generation Celery task.

Computes composite signal scores for all active stocks by combining:
- Sentiment momentum (40%): exponentially weighted avg of sentiment, half-life 6h
- Sentiment volume (25%): article count vs 20-day baseline, signed by net sentiment
- Price momentum (20%): 5-day price change, tanh-scaled to [-1, 1]
- Volume anomaly (15%): trading volume vs 20-day avg, signed by price direction
- Options (8%): put/call ratio anomaly + IV skew vs baseline (when enabled)

RSI and trend are not additive components. They classify market regime and apply
a confidence multiplier to the composite (boost when trend confirms, dampen when
the stock is technically extended or trend opposes the signal).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.signal import Signal
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.tasks.signals.component_scores import (
    calc_options_score,
    calc_price_momentum,
    calc_retail_sentiment_score,
    calc_rsi_score,
    calc_sentiment_momentum,
    calc_sentiment_volume,
    calc_trend_score,
    calc_volume_anomaly,
    get_recent_article_count,
)
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)

# ── Base weights (4 predictive components; RSI and trend are regime-only) ──
WEIGHT_SENTIMENT_MOMENTUM = 0.40
WEIGHT_SENTIMENT_VOLUME = 0.25
WEIGHT_PRICE_MOMENTUM = 0.20
WEIGHT_VOLUME_ANOMALY = 0.15

# With options only (8% added; scale other 4 down proportionally)
WEIGHT_SENTIMENT_MOMENTUM_OPT = 0.37
WEIGHT_SENTIMENT_VOLUME_OPT = 0.23
WEIGHT_PRICE_MOMENTUM_OPT = 0.18
WEIGHT_VOLUME_ANOMALY_OPT = 0.14
WEIGHT_OPTIONS = 0.08

# ── Thresholds ──
STRONG_THRESHOLD = 0.6
MODERATE_THRESHOLD = 0.35
SIGNAL_DEDUP_THRESHOLD = 0.005  # Skip new signal if score moved less than this


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
    rsi_val = rsi_score if rsi_score is not None else 0.0
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
            return composite * 1.15, regime  # trend confirms signal
        else:
            return composite * 0.85, regime  # trend opposes signal

    return composite, "sideways"


@celery_app.task(
    name="worker.tasks.signals.signal_generator.generate_all_signals",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_all_signals(self):
    """Generate composite signals for all active stocks. Called at :30 by beat."""
    try:
        return run_async(_generate_signals_async())
    except Exception as exc:
        logger.error(f"Signal generation failed: {exc}")
        raise self.retry(exc=exc)


async def _generate_signals_async() -> dict:
    """Iterate active stocks, compute scores, store signals."""
    now = datetime.now(timezone.utc)
    window_end = now
    window_start = now - timedelta(hours=1)

    signals_created = 0
    alerts_dispatched = 0
    skipped = 0
    errors = 0

    async with async_session() as session:
        result = await session.execute(
            select(Stock).where(Stock.is_active == True)  # noqa: E712
        )
        stocks = result.scalars().all()

        if not stocks:
            logger.warning("No active stocks found")
            return {"signals": 0, "alerts": 0, "errors": 0}

        # Pre-load adaptive weights (sector_id -> weights dict)
        weights_map = await _load_all_weights(session)

        # Pre-load ML models if enabled
        ml_models_map = await _load_ml_models(session) if settings.ml_ensemble_enabled else {}

        logger.info(f"Generating signals for {len(stocks)} active stocks")

        for stock in stocks:
            try:
                score_data = await _compute_composite_score(session, stock.id, now, weights_map, stock.sector_id)

                if score_data is None:
                    continue

                composite = score_data["composite"]
                direction = classify_direction(composite)
                strength = classify_strength(composite)

                # ── Dedup: skip if previous signal is materially identical ──
                last_result = await session.execute(
                    select(Signal)
                    .where(Signal.stock_id == stock.id)
                    .order_by(Signal.generated_at.desc())
                    .limit(1)
                )
                last_signal = last_result.scalars().first()

                if last_signal is not None and (
                    last_signal.direction == direction
                    and last_signal.strength == strength
                    and abs(float(last_signal.composite_score) - composite) < SIGNAL_DEDUP_THRESHOLD
                ):
                    skipped += 1
                    continue

                reasoning = _build_reasoning(
                    stock.ticker, score_data, direction, strength
                )

                # ML ensemble inference (if enabled and model available)
                ml_result = _compute_ml_score(
                    score_data, ml_models_map, stock.sector_id, direction
                ) if ml_models_map else None

                retail_sentiment = await calc_retail_sentiment_score(session, stock.id, now)

                opts_raw = score_data["options_score"]
                signal = Signal(
                    stock_id=stock.id,
                    direction=direction,
                    strength=strength,
                    composite_score=round(composite, 5),
                    sentiment_score=round(score_data["sentiment_momentum"], 5),
                    sentiment_volume_score=round(score_data["sentiment_volume"], 5),
                    price_score=round(score_data["price_momentum"], 5),
                    volume_score=round(score_data["volume_anomaly"], 5),
                    rsi_score=round(score_data["rsi_score"], 5),
                    trend_score=round(score_data["trend_score"], 5),
                    options_score=round(opts_raw, 5) if opts_raw else None,
                    article_count=score_data["article_count"],
                    reasoning=reasoning,
                    ml_score=round(ml_result.ml_score, 5) if ml_result else None,
                    ml_direction=ml_result.ml_direction if ml_result else None,
                    ml_confidence=round(ml_result.ml_confidence, 4) if ml_result else None,
                    retail_sentiment_score=round(retail_sentiment, 5) if retail_sentiment is not None else None,
                    market_regime=score_data.get("market_regime"),
                    generated_at=now,
                    window_start=window_start,
                    window_end=window_end,
                )
                session.add(signal)
                await session.flush()

                signals_created += 1

                if strength in ("strong", "moderate"):
                    _dispatch_alert_task(signal.id)
                    alerts_dispatched += 1

            except Exception as e:
                logger.error(f"Error computing signal for stock {stock.ticker}: {e}")
                errors += 1

        await session.commit()

        # Invalidate cached signal and sentiment data
        from app.core.cache import invalidate_pattern

        await invalidate_pattern("cache:signals:*")
        await invalidate_pattern("cache:sentiment:*")

    logger.info(
        f"Signal generation complete: {signals_created} signals, "
        f"{skipped} skipped (unchanged), "
        f"{alerts_dispatched} alerts dispatched, {errors} errors"
    )
    return {"signals": signals_created, "alerts": alerts_dispatched, "skipped": skipped, "errors": errors}


def _dispatch_alert_task(signal_id: int):
    """Chain alert dispatch as a separate Celery task."""
    from worker.tasks.signals.alert_dispatcher import dispatch_alerts

    dispatch_alerts.delay(signal_id)


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
    sent_volume = await calc_sentiment_volume(session, stock_id, now)
    price_mom = await calc_price_momentum(session, stock_id, now)
    vol_anomaly = await calc_volume_anomaly(session, stock_id, now)
    rsi = await calc_rsi_score(session, stock_id, now)
    trend = await calc_trend_score(session, stock_id, now)
    options = await calc_options_score(session, stock_id, now)

    article_count = await get_recent_article_count(session, stock_id, now)

    has_sentiment = sent_momentum is not None
    has_market = price_mom is not None

    if not has_sentiment and not has_market:
        return None

    sm = sent_momentum if sent_momentum is not None else 0.0
    sv = sent_volume if sent_volume is not None else 0.0
    pm = price_mom if price_mom is not None else 0.0
    va = vol_anomaly if vol_anomaly is not None else 0.0
    rsi_val = rsi if rsi is not None else 0.0
    trend_val = trend if trend is not None else 0.0
    opts_val = options if options is not None else 0.0

    w = _get_weights(weights_map, sector_id)

    # Raw composite: 4 predictive components (+ options when active)
    # RSI and trend weights are 0.0 — they do not contribute here
    raw_composite = (
        w["sentiment_momentum"] * sm
        + w["sentiment_volume"] * sv
        + w["price_momentum"] * pm
        + w["volume_anomaly"] * va
        + w.get("options", 0.0) * opts_val
    )

    # Regime classification: RSI and trend as context, not signal components
    composite, market_regime = apply_regime_multiplier(raw_composite, rsi_val, trend_val)

    return {
        "composite": composite,
        "sentiment_momentum": sm,
        "sentiment_volume": sv,
        "price_momentum": pm,
        "volume_anomaly": va,
        "rsi_score": rsi_val,
        "trend_score": trend_val,
        "options_score": opts_val,
        "market_regime": market_regime,
        "article_count": article_count,
        "weights_source": w["source"],
    }


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
            "sentiment_volume": float(row.sentiment_volume),
            "price_momentum": float(row.price_momentum),
            "volume_anomaly": float(row.volume_anomaly),
            "rsi": 0.0,  # regime only — zero weight in composite
            "trend": 0.0,  # regime only — zero weight in composite
            "options": float(row.options),
            "source": "sector" if row.sector_id else "global",
        }
        weights_map[row.sector_id] = w
    return weights_map


def _get_weights(weights_map: dict | None, sector_id: int | None) -> dict:
    """Look up adaptive weights: sector-specific -> global -> defaults.

    Adaptive weights (from SignalWeight table) contain rsi and trend columns
    which are forced to 0.0 when loaded — they are regime-only.
    """
    if weights_map:
        if sector_id is not None and sector_id in weights_map:
            return weights_map[sector_id]
        if None in weights_map:
            return weights_map[None]
    return _default_weights(has_options=settings.options_flow_enabled)


def _default_weights(has_options: bool | None = None) -> dict:
    """Return default weights for 4-component base formula.

    RSI and trend are set to 0.0 — they are no longer additive signal components.
    They are used only for regime classification via apply_regime_multiplier.
    """
    if has_options is None:
        has_options = settings.options_flow_enabled
    if has_options:
        return {
            "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM_OPT,
            "sentiment_volume": WEIGHT_SENTIMENT_VOLUME_OPT,
            "price_momentum": WEIGHT_PRICE_MOMENTUM_OPT,
            "volume_anomaly": WEIGHT_VOLUME_ANOMALY_OPT,
            "rsi": 0.0,
            "trend": 0.0,
            "options": WEIGHT_OPTIONS,
            "source": "default",
        }
    return {
        "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM,
        "sentiment_volume": WEIGHT_SENTIMENT_VOLUME,
        "price_momentum": WEIGHT_PRICE_MOMENTUM,
        "volume_anomaly": WEIGHT_VOLUME_ANOMALY,
        "rsi": 0.0,
        "trend": 0.0,
        "options": 0.0,
        "source": "default",
    }


def classify_direction(composite: float) -> str:
    if composite > 0.01:
        return "bullish"
    elif composite < -0.01:
        return "bearish"
    return "neutral"


def classify_strength(composite: float) -> str:
    abs_score = abs(composite)
    if abs_score > STRONG_THRESHOLD:
        return "strong"
    elif abs_score > MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


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

    opts_val = score_data.get("options_score", 0)
    if abs(opts_val) > 0.3:
        opts_desc = "bullish" if opts_val > 0 else "bearish"
        parts.append(f"Options flow is {opts_desc} ({opts_val:.3f})")

    regime = score_data.get("market_regime", "sideways")
    if regime not in ("sideways", None):
        regime_display = regime.replace("_", " ")
        parts.append(f"Market regime: {regime_display}")

    return ". ".join(parts) + "."


async def _load_ml_models(session: AsyncSession) -> dict:
    """Load active ML model metadata into sector_id -> model_path dict."""
    from app.models.ml_model import MLModel

    result = await session.execute(
        select(MLModel).where(MLModel.is_active == True)  # noqa: E712
    )
    rows = result.scalars().all()
    return {row.sector_id: row.model_path for row in rows}


def _compute_ml_score(
    score_data: dict,
    ml_models_map: dict,
    sector_id: int | None,
    rule_direction: str,
):
    """Look up sector or global model, run inference."""
    from worker.utils.ml_trainer import predict

    model_path = ml_models_map.get(sector_id) or ml_models_map.get(None)
    if not model_path:
        return None

    features = [
        score_data["sentiment_momentum"],
        score_data["sentiment_volume"],
        score_data["price_momentum"],
        score_data["volume_anomaly"],
        score_data["rsi_score"],
        score_data["trend_score"],
    ]
    if settings.options_flow_enabled:
        features.append(score_data["options_score"])

    return predict(
        model_path,
        features,
        rule_direction,
        confidence_threshold=settings.ml_confidence_threshold,
    )
