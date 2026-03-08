"""Component scoring functions for signal generation.

Each function computes one of the 6 signal components:
- Sentiment momentum: exponentially weighted sentiment, half-life 6h
- Sentiment volume: unique event count vs baseline, signed by net sentiment
- Price momentum: 5-day price change, tanh-scaled
- Volume anomaly: trading volume vs 20-day avg, signed by price direction
- RSI score: 14-period RSI mapped to oversold(+)/overbought(-) score
- Trend score: SMA crossover + MACD histogram combined
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_SOURCE_CREDIBILITY, SOURCE_CREDIBILITY
from app.models.article import Article
from app.models.market_data import MarketDataDaily
from app.models.sentiment import SentimentScore
from worker.utils.technical_indicators import compute_macd, compute_rsi, compute_sma

# ── Parameters ──
SENTIMENT_HALF_LIFE_HOURS = 6
BASELINE_DAYS = 20
PRICE_MOMENTUM_DAYS = 5
RSI_LOOKBACK_DAYS = 30
TREND_LOOKBACK_DAYS = 60


async def calc_sentiment_momentum(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Exponentially weighted average of sentiment scores, half-life 6h.

    Sentiment value per score = positive - negative (range: [-1, 1]).
    Weight = exp(-ln(2) * hours_ago / half_life) * source_credibility.
    Deduplication: for each duplicate group, only the highest-credibility score is kept.
    """
    since = now - timedelta(hours=48)
    result = await session.execute(
        select(
            SentimentScore.positive_score,
            SentimentScore.negative_score,
            SentimentScore.processed_at,
            Article.source,
            Article.duplicate_group_id,
        )
        .join(Article, SentimentScore.article_id == Article.id)
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
        .order_by(SentimentScore.processed_at.desc())
    )
    rows = result.all()

    if not rows:
        return None

    # Deduplicate: for each duplicate group, keep the highest-credibility source
    seen_groups: dict[int, float] = {}  # group_id -> best credibility
    deduped_rows = []
    for row in rows:
        credibility = SOURCE_CREDIBILITY.get(row.source, DEFAULT_SOURCE_CREDIBILITY)
        group_id = row.duplicate_group_id
        if group_id is not None:
            if group_id in seen_groups:
                if credibility <= seen_groups[group_id]:
                    continue  # skip lower-credibility duplicate
            seen_groups[group_id] = credibility
        deduped_rows.append((row, credibility))

    if not deduped_rows:
        return None

    decay_rate = math.log(2) / SENTIMENT_HALF_LIFE_HOURS
    weighted_sum = 0.0
    weight_total = 0.0

    for row, credibility in deduped_rows:
        sentiment_value = float(row.positive_score) - float(row.negative_score)
        hours_ago = (now - row.processed_at).total_seconds() / 3600
        weight = math.exp(-decay_rate * hours_ago) * credibility
        weighted_sum += sentiment_value * weight
        weight_total += weight

    if weight_total == 0:
        return None

    return weighted_sum / weight_total


async def calc_sentiment_volume(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Unique event count in last 24h vs 20-day daily baseline.

    Deduplicates by duplicate_group_id (NULL groups count individually).
    Magnitude via tanh, signed by net sentiment direction.
    """
    since_24h = now - timedelta(hours=24)
    recent_result = await session.execute(
        select(
            SentimentScore.id,
            SentimentScore.positive_score,
            SentimentScore.negative_score,
            Article.duplicate_group_id,
        )
        .join(Article, SentimentScore.article_id == Article.id)
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since_24h)
    )
    recent_rows = recent_result.all()

    if not recent_rows:
        return None

    # Count unique events: distinct duplicate_group_id, NULLs count individually
    seen_groups: set[int] = set()
    unique_count = 0
    net_sentiment_sum = 0.0
    for row in recent_rows:
        net_sentiment_sum += float(row.positive_score) - float(row.negative_score)
        if row.duplicate_group_id is not None:
            if row.duplicate_group_id in seen_groups:
                continue
            seen_groups.add(row.duplicate_group_id)
        unique_count += 1

    recent_net_sentiment = net_sentiment_sum / len(recent_rows) if recent_rows else 0.0

    if unique_count == 0:
        return None

    since_20d = now - timedelta(days=BASELINE_DAYS)
    baseline_result = await session.execute(
        select(SentimentScore.id, Article.duplicate_group_id)
        .join(Article, SentimentScore.article_id == Article.id)
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since_20d)
        .where(SentimentScore.processed_at < since_24h)
    )
    baseline_rows = baseline_result.all()
    baseline_groups: set[int] = set()
    baseline_unique = 0
    for row in baseline_rows:
        if row.duplicate_group_id is not None:
            if row.duplicate_group_id in baseline_groups:
                continue
            baseline_groups.add(row.duplicate_group_id)
        baseline_unique += 1

    baseline_daily_avg = baseline_unique / max(BASELINE_DAYS - 1, 1)

    if baseline_daily_avg == 0:
        ratio = min(unique_count, 5.0)
    else:
        ratio = unique_count / baseline_daily_avg

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
    """RSI-based score: oversold (<30) -> positive, overbought (>70) -> negative."""
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

    # Center at 50, scale so edges hit ~1: RSI<30 -> positive, RSI>70 -> negative
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


async def get_recent_article_count(
    session: AsyncSession, stock_id: int, now: datetime
) -> int:
    """Count unique events (deduplicated by duplicate_group_id) in the last 24h."""
    since = now - timedelta(hours=24)
    result = await session.execute(
        select(Article.duplicate_group_id)
        .join(SentimentScore, SentimentScore.article_id == Article.id)
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
    )
    rows = result.all()
    seen_groups: set[int] = set()
    unique_count = 0
    for row in rows:
        if row.duplicate_group_id is not None:
            if row.duplicate_group_id in seen_groups:
                continue
            seen_groups.add(row.duplicate_group_id)
        unique_count += 1
    return unique_count
