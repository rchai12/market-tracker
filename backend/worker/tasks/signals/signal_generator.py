"""Signal generation Celery task.

Computes composite signal scores for all active stocks by combining:
- Sentiment momentum (40%): exponentially weighted avg of sentiment, half-life 6h
- Sentiment volume (25%): article count vs 20-day baseline, signed by net sentiment
- Price momentum (20%): 5-day price change, tanh-scaled to [-1, 1]
- Volume anomaly (15%): trading volume vs 20-day avg, signed by price direction
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.market_data import MarketDataDaily
from app.models.sentiment import SentimentScore
from app.models.signal import Signal
from app.models.stock import Stock
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Scoring weights ──
WEIGHT_SENTIMENT_MOMENTUM = 0.40
WEIGHT_SENTIMENT_VOLUME = 0.25
WEIGHT_PRICE_MOMENTUM = 0.20
WEIGHT_VOLUME_ANOMALY = 0.15

# ── Parameters ──
SENTIMENT_HALF_LIFE_HOURS = 6
BASELINE_DAYS = 20
PRICE_MOMENTUM_DAYS = 5

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
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_generate_signals_async())
        return result
    except Exception as exc:
        logger.error(f"Signal generation failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()


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

        logger.info(f"Generating signals for {len(stocks)} active stocks")

        for stock in stocks:
            try:
                score_data = await _compute_composite_score(session, stock.id, now)

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
    session: AsyncSession, stock_id: int, now: datetime
) -> dict | None:
    """Compute all four components and the weighted composite for a stock."""
    sent_momentum = await calc_sentiment_momentum(session, stock_id, now)
    sent_volume = await calc_sentiment_volume(session, stock_id, now)
    price_mom = await calc_price_momentum(session, stock_id, now)
    vol_anomaly = await calc_volume_anomaly(session, stock_id, now)

    article_count = await _get_recent_article_count(session, stock_id, now)

    has_sentiment = sent_momentum is not None
    has_market = price_mom is not None

    if not has_sentiment and not has_market:
        return None

    sm = sent_momentum if sent_momentum is not None else 0.0
    sv = sent_volume if sent_volume is not None else 0.0
    pm = price_mom if price_mom is not None else 0.0
    va = vol_anomaly if vol_anomaly is not None else 0.0

    composite = (
        WEIGHT_SENTIMENT_MOMENTUM * sm
        + WEIGHT_SENTIMENT_VOLUME * sv
        + WEIGHT_PRICE_MOMENTUM * pm
        + WEIGHT_VOLUME_ANOMALY * va
    )

    return {
        "composite": composite,
        "sentiment_momentum": sm,
        "sentiment_volume": sv,
        "price_momentum": pm,
        "volume_anomaly": va,
        "article_count": article_count,
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

    return ". ".join(parts) + "."
