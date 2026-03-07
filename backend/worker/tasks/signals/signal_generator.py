"""Signal generation Celery task.

Computes composite signal scores for all active stocks by combining:
- Sentiment momentum (30%): exponentially weighted avg of sentiment, half-life 6h
- Sentiment volume (20%): article count vs 20-day baseline, signed by net sentiment
- Price momentum (15%): 5-day price change, tanh-scaled to [-1, 1]
- Volume anomaly (10%): trading volume vs 20-day avg, signed by price direction
- RSI (15%): 14-period RSI mapped to oversold(+)/overbought(-) score
- Trend (10%): SMA crossover + MACD histogram combined score
"""

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.market_data import MarketDataDaily
from app.models.sentiment import SentimentScore
from app.models.signal import Signal
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async
from worker.utils.technical_indicators import compute_macd, compute_rsi, compute_sma

logger = logging.getLogger(__name__)

# ── Scoring weights (6 components, sum to 1.0) ──
WEIGHT_SENTIMENT_MOMENTUM = 0.30
WEIGHT_SENTIMENT_VOLUME = 0.20
WEIGHT_PRICE_MOMENTUM = 0.15
WEIGHT_VOLUME_ANOMALY = 0.10
WEIGHT_RSI = 0.15
WEIGHT_TREND = 0.10

# ── Parameters ──
SENTIMENT_HALF_LIFE_HOURS = 6
BASELINE_DAYS = 20
PRICE_MOMENTUM_DAYS = 5
RSI_LOOKBACK_DAYS = 30
TREND_LOOKBACK_DAYS = 60

# ── Thresholds ──
STRONG_THRESHOLD = 0.6
MODERATE_THRESHOLD = 0.35


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

        logger.info(f"Generating signals for {len(stocks)} active stocks")

        for stock in stocks:
            try:
                score_data = await _compute_composite_score(session, stock.id, now, weights_map, stock.sector_id)

                if score_data is None:
                    continue

                composite = score_data["composite"]
                direction = classify_direction(composite)
                strength = classify_strength(composite)

                reasoning = _build_reasoning(
                    stock.ticker, score_data, direction, strength
                )

                signal = Signal(
                    stock_id=stock.id,
                    direction=direction,
                    strength=strength,
                    composite_score=round(composite, 5),
                    sentiment_score=round(score_data["sentiment_momentum"], 5),
                    price_score=round(score_data["price_momentum"], 5),
                    volume_score=round(score_data["volume_anomaly"], 5),
                    rsi_score=round(score_data["rsi_score"], 5),
                    trend_score=round(score_data["trend_score"], 5),
                    article_count=score_data["article_count"],
                    reasoning=reasoning,
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

    logger.info(
        f"Signal generation complete: {signals_created} signals, "
        f"{alerts_dispatched} alerts dispatched, {errors} errors"
    )
    return {"signals": signals_created, "alerts": alerts_dispatched, "errors": errors}


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
    """Compute all six components and the weighted composite for a stock."""
    sent_momentum = await calc_sentiment_momentum(session, stock_id, now)
    sent_volume = await calc_sentiment_volume(session, stock_id, now)
    price_mom = await calc_price_momentum(session, stock_id, now)
    vol_anomaly = await calc_volume_anomaly(session, stock_id, now)
    rsi = await calc_rsi_score(session, stock_id, now)
    trend = await calc_trend_score(session, stock_id, now)

    article_count = await _get_recent_article_count(session, stock_id, now)

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

    # Use adaptive weights if available, otherwise default
    w = _get_weights(weights_map, sector_id)

    composite = (
        w["sentiment_momentum"] * sm
        + w["sentiment_volume"] * sv
        + w["price_momentum"] * pm
        + w["volume_anomaly"] * va
        + w["rsi"] * rsi_val
        + w["trend"] * trend_val
    )

    return {
        "composite": composite,
        "sentiment_momentum": sm,
        "sentiment_volume": sv,
        "price_momentum": pm,
        "volume_anomaly": va,
        "rsi_score": rsi_val,
        "trend_score": trend_val,
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
        weights_map[row.sector_id] = {
            "sentiment_momentum": float(row.sentiment_momentum),
            "sentiment_volume": float(row.sentiment_volume),
            "price_momentum": float(row.price_momentum),
            "volume_anomaly": float(row.volume_anomaly),
            "rsi": float(row.rsi),
            "trend": float(row.trend),
            "source": "sector" if row.sector_id else "global",
        }
    return weights_map


def _get_weights(weights_map: dict | None, sector_id: int | None) -> dict:
    """Look up adaptive weights: sector-specific → global → defaults."""
    if weights_map:
        if sector_id is not None and sector_id in weights_map:
            return weights_map[sector_id]
        if None in weights_map:
            return weights_map[None]
    return _default_weights()


def _default_weights() -> dict:
    return {
        "sentiment_momentum": WEIGHT_SENTIMENT_MOMENTUM,
        "sentiment_volume": WEIGHT_SENTIMENT_VOLUME,
        "price_momentum": WEIGHT_PRICE_MOMENTUM,
        "volume_anomaly": WEIGHT_VOLUME_ANOMALY,
        "rsi": WEIGHT_RSI,
        "trend": WEIGHT_TREND,
        "source": "default",
    }


async def calc_sentiment_momentum(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Exponentially weighted average of sentiment scores, half-life 6h.

    Sentiment value per score = positive - negative (range: [-1, 1]).
    Weight = exp(-ln(2) * hours_ago / half_life).
    """
    since = now - timedelta(hours=48)
    result = await session.execute(
        select(
            SentimentScore.positive_score,
            SentimentScore.negative_score,
            SentimentScore.processed_at,
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
        .order_by(SentimentScore.processed_at.desc())
    )
    rows = result.all()

    if not rows:
        return None

    decay_rate = math.log(2) / SENTIMENT_HALF_LIFE_HOURS
    weighted_sum = 0.0
    weight_total = 0.0

    for row in rows:
        sentiment_value = float(row.positive_score) - float(row.negative_score)
        hours_ago = (now - row.processed_at).total_seconds() / 3600
        weight = math.exp(-decay_rate * hours_ago)
        weighted_sum += sentiment_value * weight
        weight_total += weight

    if weight_total == 0:
        return None

    return weighted_sum / weight_total


async def calc_sentiment_volume(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Article count in last 24h vs 20-day daily baseline.

    Magnitude via tanh, signed by net sentiment direction.
    """
    since_24h = now - timedelta(hours=24)
    recent_result = await session.execute(
        select(
            func.count(SentimentScore.id),
            func.avg(SentimentScore.positive_score - SentimentScore.negative_score),
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since_24h)
    )
    recent_row = recent_result.one()
    recent_count = recent_row[0] or 0
    recent_net_sentiment = float(recent_row[1]) if recent_row[1] is not None else 0.0

    if recent_count == 0:
        return None

    since_20d = now - timedelta(days=BASELINE_DAYS)
    baseline_result = await session.execute(
        select(func.count(SentimentScore.id))
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since_20d)
        .where(SentimentScore.processed_at < since_24h)
    )
    baseline_total = baseline_result.scalar() or 0
    baseline_daily_avg = baseline_total / max(BASELINE_DAYS - 1, 1)

    if baseline_daily_avg == 0:
        ratio = min(recent_count, 5.0)
    else:
        ratio = recent_count / baseline_daily_avg

    magnitude = math.tanh(ratio - 1.0)
    direction_sign = 1.0 if recent_net_sentiment >= 0 else -1.0

    return magnitude * direction_sign


async def calc_price_momentum(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """5-day price change, tanh-scaled to [-1, 1]."""
    result = await session.execute(
        select(MarketDataDaily.close, MarketDataDaily.date)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.close != None)  # noqa: E711
        .order_by(MarketDataDaily.date.desc())
        .limit(PRICE_MOMENTUM_DAYS + 1)
    )
    rows = result.all()

    if len(rows) < 2:
        return None

    latest_close = float(rows[0].close)
    oldest_close = float(rows[-1].close)

    if oldest_close == 0:
        return None

    pct_change = (latest_close - oldest_close) / oldest_close
    return math.tanh(pct_change * 5)


async def calc_volume_anomaly(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Trading volume vs 20-day average, signed by price direction."""
    result = await session.execute(
        select(MarketDataDaily.volume, MarketDataDaily.close, MarketDataDaily.date)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.volume != None)  # noqa: E711
        .order_by(MarketDataDaily.date.desc())
        .limit(BASELINE_DAYS + 1)
    )
    rows = result.all()

    if len(rows) < 3:
        return None

    latest_volume = rows[0].volume
    latest_close = float(rows[0].close) if rows[0].close else None
    prev_close = float(rows[1].close) if rows[1].close else None

    volumes = [r.volume for r in rows[1:] if r.volume and r.volume > 0]
    if not volumes:
        return None

    avg_volume = sum(volumes) / len(volumes)
    if avg_volume == 0:
        return None

    ratio = latest_volume / avg_volume
    magnitude = math.tanh(ratio - 1.0)

    if latest_close is not None and prev_close is not None and prev_close > 0:
        price_direction = 1.0 if latest_close >= prev_close else -1.0
    else:
        price_direction = 1.0

    return magnitude * price_direction


async def calc_rsi_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """RSI-based score: oversold (<30) → positive, overbought (>70) → negative."""
    result = await session.execute(
        select(MarketDataDaily.close)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.close != None)  # noqa: E711
        .order_by(MarketDataDaily.date.desc())
        .limit(RSI_LOOKBACK_DAYS)
    )
    rows = result.all()

    if len(rows) < 16:  # Need at least 14+1 for RSI + 1 for warmup
        return None

    closes = [float(r.close) for r in reversed(rows)]
    rsi_values = compute_rsi(closes, period=14)
    latest_rsi = rsi_values[-1]
    if latest_rsi is None:
        return None

    # Center at 50, scale so edges hit ~1: RSI<30 → positive, RSI>70 → negative
    centered = (50 - latest_rsi) / 50
    return math.tanh(centered * 2.5)


async def calc_trend_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Combined SMA crossover + MACD crossover trend score."""
    result = await session.execute(
        select(MarketDataDaily.close)
        .where(MarketDataDaily.stock_id == stock_id)
        .where(MarketDataDaily.close != None)  # noqa: E711
        .order_by(MarketDataDaily.date.desc())
        .limit(TREND_LOOKBACK_DAYS)
    )
    rows = result.all()

    if len(rows) < 52:  # Need 50 for SMA50 + buffer
        return None

    closes = [float(r.close) for r in reversed(rows)]

    # SMA crossover component
    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    sma_score = 0.0
    if sma20[-1] is not None and sma50[-1] is not None and sma50[-1] != 0:
        sma_diff = (sma20[-1] - sma50[-1]) / sma50[-1]
        sma_score = math.tanh(sma_diff * 10)

    # MACD crossover component
    macd_data = compute_macd(closes)
    macd_score = 0.0
    latest_macd = macd_data[-1]
    if latest_macd["histogram"] is not None and closes[-1] != 0:
        norm_hist = latest_macd["histogram"] / closes[-1]
        macd_score = math.tanh(norm_hist * 100)

    # Combine: SMA crossover (60%) + MACD (40%)
    return 0.6 * sma_score + 0.4 * macd_score


async def _get_recent_article_count(
    session: AsyncSession, stock_id: int, now: datetime
) -> int:
    """Count sentiment-scored articles in the last 24h for this stock."""
    since = now - timedelta(hours=24)
    result = await session.execute(
        select(func.count(SentimentScore.id))
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
    )
    return result.scalar() or 0


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

    rsi_val = score_data.get("rsi_score", 0)
    if abs(rsi_val) > 0.3:
        rsi_desc = "oversold" if rsi_val > 0 else "overbought"
        parts.append(f"RSI indicates {rsi_desc} ({rsi_val:.3f})")

    trend_val = score_data.get("trend_score", 0)
    if abs(trend_val) > 0.2:
        trend_desc = "uptrend" if trend_val > 0 else "downtrend"
        parts.append(f"Technical trend is {trend_desc} ({trend_val:.3f})")

    return ". ".join(parts) + "."
