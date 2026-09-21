"""Signal generation Celery task.

Computes composite signal scores for all active stocks by combining:
- Sentiment momentum (40%): exponentially weighted avg of sentiment, half-life 6h
- Sentiment volume (25%): article count vs 20-day baseline, signed by net sentiment
- Price momentum (20%): 5-day price change, tanh-scaled to [-1, 1]
- Volume anomaly (15%): trading volume vs 20-day avg, signed by price direction
- Earnings surprise (10%): EPS beat/miss vs consensus, active only within 48h of report
- Options (8%): put/call ratio anomaly + IV skew vs baseline (when enabled)
- Analyst ratings (7%): 30-day LLM-extracted upgrades/downgrades + price-target upside
- ML ensemble (8%): LightGBM score, gated when the model meets accuracy/sample floors
- Insider trading (8%): 30-day Form 4 net buying, role-weighted, sells discounted

RSI and trend are not additive components. They classify market regime and apply
a confidence multiplier to the composite (boost when trend confirms, dampen when
the stock is technically extended or trend opposes the signal).
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.daily_signal_view import DailySignalView
from app.models.market_data import MarketDataDaily
from app.models.regime_adaptive_weight import RegimeAdaptiveWeight
from app.models.signal import Signal
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.tasks.signals.component_scores import (
    calc_analyst_score,
    calc_earnings_surprise_score,
    calc_insider_score,
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
from worker.utils.daily_aggregation import ET, bucket_signals, compute_net_view, trading_date_lower_bound
from worker.utils.signal_formula import (
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
    WEIGHT_ANALYST,
    WEIGHT_EARNINGS,
    WEIGHT_INSIDER,
    WEIGHT_ML,
    WEIGHT_OPTIONS,
    WEIGHT_PRICE_MOMENTUM,
    WEIGHT_PRICE_MOMENTUM_BOTH,
    WEIGHT_PRICE_MOMENTUM_EARN,
    WEIGHT_PRICE_MOMENTUM_OPT,
    WEIGHT_SENTIMENT_MOMENTUM,
    WEIGHT_SENTIMENT_MOMENTUM_BOTH,
    WEIGHT_SENTIMENT_MOMENTUM_EARN,
    WEIGHT_SENTIMENT_MOMENTUM_OPT,
    WEIGHT_SENTIMENT_VOLUME,
    WEIGHT_SENTIMENT_VOLUME_BOTH,
    WEIGHT_SENTIMENT_VOLUME_EARN,
    WEIGHT_SENTIMENT_VOLUME_OPT,
    WEIGHT_VOLUME_ANOMALY,
    WEIGHT_VOLUME_ANOMALY_BOTH,
    WEIGHT_VOLUME_ANOMALY_EARN,
    WEIGHT_VOLUME_ANOMALY_OPT,
    apply_regime_multiplier,
    classify_direction,
    classify_regime,
    classify_strength,
    combine_component_scores,
    default_weights,
    ml_model_qualifies,
    resolve_weights,
)

logger = logging.getLogger(__name__)

# Skip new signal if score moved less than this
SIGNAL_DEDUP_THRESHOLD = 0.005


# Re-exports so existing tests keep importing from this module.
def _default_weights(
    has_options: bool | None = None,
    has_earnings: bool = False,
    has_analyst: bool = False,
    has_ml: bool = False,
    has_insider: bool = False,
) -> dict:
    if has_options is None:
        has_options = settings.options_flow_enabled
    return default_weights(
        has_options=has_options,
        has_earnings=has_earnings,
        has_analyst=has_analyst,
        has_ml=has_ml,
        has_insider=has_insider,
    )


def _get_weights(
    weights_map: dict | None,
    sector_id: int | None,
    has_earnings: bool = False,
    has_options: bool | None = None,
    has_analyst: bool = False,
    has_ml: bool = False,
    has_insider: bool = False,
    market_regime: str | None = None,
    regime_weights_map: dict | None = None,
) -> dict:
    if has_options is None:
        has_options = settings.options_flow_enabled
    return resolve_weights(
        weights_map,
        sector_id,
        has_earnings,
        has_options,
        has_analyst=has_analyst,
        has_ml=has_ml,
        has_insider=has_insider,
        market_regime=market_regime,
        regime_weights_map=regime_weights_map,
    )


__all__ = [
    "MODERATE_THRESHOLD",
    "SIGNAL_DEDUP_THRESHOLD",
    "STRONG_THRESHOLD",
    "WEIGHT_ANALYST",
    "WEIGHT_EARNINGS",
    "WEIGHT_INSIDER",
    "WEIGHT_ML",
    "WEIGHT_OPTIONS",
    "WEIGHT_PRICE_MOMENTUM",
    "WEIGHT_PRICE_MOMENTUM_BOTH",
    "WEIGHT_PRICE_MOMENTUM_EARN",
    "WEIGHT_PRICE_MOMENTUM_OPT",
    "WEIGHT_SENTIMENT_MOMENTUM",
    "WEIGHT_SENTIMENT_MOMENTUM_BOTH",
    "WEIGHT_SENTIMENT_MOMENTUM_EARN",
    "WEIGHT_SENTIMENT_MOMENTUM_OPT",
    "WEIGHT_SENTIMENT_VOLUME",
    "WEIGHT_SENTIMENT_VOLUME_BOTH",
    "WEIGHT_SENTIMENT_VOLUME_EARN",
    "WEIGHT_SENTIMENT_VOLUME_OPT",
    "WEIGHT_VOLUME_ANOMALY",
    "WEIGHT_VOLUME_ANOMALY_BOTH",
    "WEIGHT_VOLUME_ANOMALY_EARN",
    "WEIGHT_VOLUME_ANOMALY_OPT",
    "apply_regime_multiplier",
    "classify_direction",
    "classify_strength",
    "generate_all_signals",
    "_default_weights",
    "_get_weights",
]


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


async def _generate_signals_async(now: datetime | None = None) -> dict:
    """Iterate active stocks, compute scores, store signals."""
    now = now or datetime.now(UTC)
    if now.astimezone(ET).weekday() >= 5:
        logger.info("Skipping signal generation: weekend")
        return {"skipped": True, "reason": "weekend"}

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
        regime_weights_map = await _load_regime_weights(session)

        # Pre-load ML models if enabled
        ml_models_map = await _load_ml_models(session) if settings.ml_ensemble_enabled else {}

        logger.info(f"Generating signals for {len(stocks)} active stocks")

        for stock in stocks:
            try:
                score_data = await _compute_composite_score(
                    session, stock.id, now, weights_map, stock.sector_id, regime_weights_map
                )

                if score_data is None:
                    continue

                # First-pass direction signs ML inference; promotion may recombine.
                first_direction = classify_direction(score_data["composite"])
                ml_model = _resolve_ml_model(ml_models_map, stock.sector_id) if ml_models_map else None
                ml_result = (
                    _compute_ml_score(score_data, ml_model, first_direction) if ml_model is not None else None
                )
                has_ml = (
                    ml_result is not None
                    and ml_model is not None
                    and ml_model_qualifies(ml_model.validation_accuracy, ml_model.training_samples)
                )
                if has_ml:
                    promoted = _recombine_with_ml(
                        score_data, weights_map, stock.sector_id, regime_weights_map, ml_result.ml_score
                    )
                    if promoted is not None:
                        score_data = promoted
                    else:
                        has_ml = False

                composite = score_data["composite"]
                direction = classify_direction(composite)
                strength = classify_strength(composite)

                # ── Dedup: skip if previous signal is materially identical ──
                last_result = await session.execute(
                    select(Signal).where(Signal.stock_id == stock.id).order_by(Signal.generated_at.desc()).limit(1)
                )
                last_signal = last_result.scalars().first()

                if last_signal is not None and (
                    last_signal.direction == direction
                    and last_signal.strength == strength
                    and abs(float(last_signal.composite_score) - composite) < SIGNAL_DEDUP_THRESHOLD
                ):
                    skipped += 1
                    continue

                reasoning = _build_reasoning(stock.ticker, score_data, direction, strength, has_ml=has_ml)

                retail_sentiment = await calc_retail_sentiment_score(session, stock.id, now)

                opts_raw = score_data["options_score"]
                earn_raw = score_data["earnings_score"]
                analyst_raw = score_data["analyst_score"]
                insider_raw = score_data.get("insider_score")
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
                    options_score=round(opts_raw, 5) if opts_raw is not None else None,
                    article_count=score_data["article_count"],
                    reasoning=reasoning,
                    ml_score=round(ml_result.ml_score, 5) if ml_result else None,
                    ml_direction=ml_result.ml_direction if ml_result else None,
                    ml_confidence=round(ml_result.ml_confidence, 4) if ml_result else None,
                    has_ml=has_ml,
                    retail_sentiment_score=round(retail_sentiment, 5) if retail_sentiment is not None else None,
                    market_regime=score_data.get("market_regime"),
                    earnings_score=round(earn_raw, 5) if earn_raw is not None else None,
                    analyst_score=round(analyst_raw, 5) if analyst_raw is not None else None,
                    insider_score=round(insider_raw, 5) if insider_raw is not None else None,
                    generated_at=now,
                    trading_date=await _resolve_trading_date(session, stock.id, now),
                    window_start=window_start,
                    window_end=window_end,
                )
                session.add(signal)
                await session.flush()
                await _upsert_daily_view(session, stock.id, signal.trading_date)

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


async def _resolve_trading_date(session: AsyncSession, stock_id: int, generated_at: datetime) -> date:
    """Next market close this signal is predicting, from market_data_daily."""
    floor = trading_date_lower_bound(generated_at)
    result = await session.execute(
        select(MarketDataDaily.date)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.date >= floor)
        .order_by(MarketDataDaily.date.asc())
        .limit(1)
    )
    found = result.scalar_one_or_none()
    if found is not None:
        return found
    fallback = await session.execute(
        select(MarketDataDaily.date)
        .where(MarketDataDaily.date >= floor)
        .order_by(MarketDataDaily.date.asc())
        .limit(1)
    )
    any_date = fallback.scalar_one_or_none()
    return any_date if any_date is not None else floor


async def _upsert_daily_view(session: AsyncSession, stock_id: int, trading_date: date | None) -> None:
    """Rebuild the net view for (stock, trading_date). Skip empty groups.

    Hourly signals are reduced to one strongest |composite| per 4-hour ET
    bucket, then recency-weighted toward the session close.
    """
    if trading_date is None:
        return
    result = await session.execute(
        select(Signal)
        .where(Signal.stock_id == stock_id)
        .where(Signal.trading_date == trading_date)
        .where(Signal.composite_score.isnot(None))
    )
    signals = list(result.scalars().all())
    raw_signal_count = len(signals)
    view = compute_net_view(bucket_signals(signals), trading_date)
    if view is None:
        return
    stmt = pg_insert(DailySignalView).values(
        stock_id=stock_id,
        trading_date=trading_date,
        net_score=round(view.net_score, 6),
        direction=view.direction,
        conviction=round(view.conviction, 6),
        signal_count=view.signal_count,
        raw_signal_count=raw_signal_count,
        updated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_daily_signal_views_stock_date",
        set_={
            "net_score": stmt.excluded.net_score,
            "direction": stmt.excluded.direction,
            "conviction": stmt.excluded.conviction,
            "signal_count": stmt.excluded.signal_count,
            "raw_signal_count": stmt.excluded.raw_signal_count,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.execute(stmt)


async def _compute_composite_score(
    session: AsyncSession,
    stock_id: int,
    now: datetime,
    weights_map: dict | None = None,
    sector_id: int | None = None,
    regime_weights_map: dict | None = None,
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
    earnings = await calc_earnings_surprise_score(session, stock_id, now)
    analyst = await calc_analyst_score(session, stock_id, now)
    insider = await calc_insider_score(session, stock_id, now)

    article_count = await get_recent_article_count(session, stock_id, now)

    has_earnings = earnings is not None
    has_analyst = analyst is not None
    has_insider = insider is not None
    w = _get_weights(
        weights_map,
        sector_id,
        has_earnings=has_earnings,
        has_analyst=has_analyst,
        has_insider=has_insider,
        market_regime=classify_regime(rsi, trend),
        regime_weights_map=regime_weights_map,
    )

    return combine_component_scores(
        sentiment_momentum=sent_momentum,
        sentiment_volume=sent_volume,
        price_momentum=price_mom,
        volume_anomaly=vol_anomaly,
        rsi_score=rsi,
        trend_score=trend,
        options_score=options,
        earnings_score=earnings,
        analyst_score=analyst,
        insider_score=insider,
        weights=w,
        has_options=settings.options_flow_enabled,
        article_count=article_count,
    )


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
            "earnings": float(row.earnings) if row.earnings is not None else 0.0,
            "analyst": float(row.analyst) if row.analyst is not None else 0.0,
            "ml": 0.0,
            "insider": float(row.insider) if getattr(row, "insider", None) is not None else 0.0,
            "source": "sector" if row.sector_id else "global",
        }
        weights_map[row.sector_id] = w
    return weights_map


async def _load_regime_weights(session: AsyncSession) -> dict:
    """Pre-load (sector_id, regime) -> weights for resolve_weights fallback chain."""
    if not settings.feedback_enabled:
        return {}

    result = await session.execute(
        select(RegimeAdaptiveWeight).where(RegimeAdaptiveWeight.sample_count >= settings.feedback_min_samples)
    )
    rows = result.scalars().all()
    regime_map: dict = {}
    for row in rows:
        regime_map[(row.sector_id, row.regime)] = {
            "sentiment_momentum": float(row.sentiment_momentum),
            "sentiment_volume": float(row.sentiment_volume),
            "price_momentum": float(row.price_momentum),
            "volume_anomaly": float(row.volume_anomaly),
            "rsi": 0.0,
            "trend": 0.0,
            "options": float(row.options),
            "earnings": float(row.earnings) if row.earnings is not None else 0.0,
            "analyst": float(row.analyst) if row.analyst is not None else 0.0,
            "ml": 0.0,
            "insider": float(row.insider) if getattr(row, "insider", None) is not None else 0.0,
            "source": "regime",
        }
    return regime_map


def _build_reasoning(ticker: str, score_data: dict, direction: str, strength: str, has_ml: bool = False) -> str:
    """Generate human-readable reasoning string for the signal."""
    parts = [f"{ticker}: {strength} {direction} signal (score: {score_data['composite']:.3f})"]

    sm = score_data["sentiment_momentum"]
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

    opts_val = score_data.get("options_score")
    if opts_val is not None and abs(opts_val) > 0.3:
        opts_desc = "bullish" if opts_val > 0 else "bearish"
        parts.append(f"Options flow is {opts_desc} ({opts_val:.3f})")

    earn_val = score_data.get("earnings_score")
    if earn_val is not None and abs(earn_val) > 0.2:
        earn_dir = "beat" if earn_val > 0 else "miss"
        parts.append(f"Recent earnings {earn_dir} (score: {earn_val:.3f})")

    analyst_val = score_data.get("analyst_score")
    if analyst_val is not None and abs(analyst_val) > 0.2:
        analyst_dir = "bullish" if analyst_val > 0 else "bearish"
        parts.append(f"Analyst ratings are {analyst_dir} ({analyst_val:.3f})")

    insider_val = score_data.get("insider_score")
    if insider_val is not None and abs(insider_val) > 0.2:
        insider_dir = "buying" if insider_val > 0 else "selling"
        parts.append(f"Insider activity is net {insider_dir} ({insider_val:.3f})")

    ml_val = score_data.get("ml_score")
    if has_ml and ml_val is not None and abs(ml_val) > 0.2:
        ml_dir = "bullish" if ml_val > 0 else "bearish"
        parts.append(f"ML ensemble is {ml_dir} ({ml_val:.3f})")

    regime = score_data.get("market_regime", "sideways")
    if regime not in ("sideways", None):
        regime_display = regime.replace("_", " ")
        parts.append(f"Market regime: {regime_display}")

    return ". ".join(parts) + "."


async def _load_ml_models(session: AsyncSession) -> dict:
    """Load active ML model rows into a sector_id -> MLModel dict."""
    from app.models.ml_model import MLModel

    result = await session.execute(
        select(MLModel).where(MLModel.is_active == True)  # noqa: E712
    )
    rows = result.scalars().all()
    return {row.sector_id: row for row in rows}


def _resolve_ml_model(ml_models_map: dict, sector_id: int | None):
    """Prefer a sector model, then the global (sector_id is None) fallback."""
    return ml_models_map.get(sector_id) or ml_models_map.get(None)


def _compute_ml_score(score_data: dict, ml_model, rule_direction: str):
    """Run inference against a loaded MLModel row."""
    from worker.utils.ml_trainer import build_feature_vector, predict

    if ml_model is None or not ml_model.model_path:
        return None

    # Must match training FEATURE_NAMES (6 components). Do not append options
    # or earnings — that would mismatch the trained LightGBM feature dim.
    features = build_feature_vector(score_data)

    return predict(
        ml_model.model_path,
        features,
        rule_direction,
        confidence_threshold=settings.ml_confidence_threshold,
    )


def _recombine_with_ml(
    score_data: dict,
    weights_map: dict | None,
    sector_id: int | None,
    regime_weights_map: dict | None,
    ml_score: float,
) -> dict | None:
    """Re-run the composite with a qualifying ML score in the gated pool."""
    has_earnings = score_data["earnings_score"] is not None
    has_analyst = score_data["analyst_score"] is not None
    has_insider = score_data.get("insider_score") is not None
    w = _get_weights(
        weights_map,
        sector_id,
        has_earnings=has_earnings,
        has_analyst=has_analyst,
        has_ml=True,
        has_insider=has_insider,
        market_regime=score_data.get("market_regime"),
        regime_weights_map=regime_weights_map,
    )
    return combine_component_scores(
        sentiment_momentum=score_data["sentiment_momentum"],
        sentiment_volume=score_data["sentiment_volume"],
        price_momentum=score_data["price_momentum"],
        volume_anomaly=score_data["volume_anomaly"],
        rsi_score=score_data["rsi_score"],
        trend_score=score_data["trend_score"],
        options_score=score_data["options_score"],
        earnings_score=score_data["earnings_score"],
        analyst_score=score_data["analyst_score"],
        ml_score=ml_score,
        has_ml=True,
        insider_score=score_data.get("insider_score"),
        weights=w,
        has_options=settings.options_flow_enabled,
        article_count=score_data["article_count"],
    )
