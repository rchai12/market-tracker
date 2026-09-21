"""Component scoring functions for signal generation.

Each function computes one of the signal components:
- Sentiment momentum: exponentially weighted sentiment, half-life 6h
- Sentiment volume: unique event count vs baseline, signed by net sentiment
- Price momentum: 5-day price change, tanh-scaled
- Volume anomaly: trading volume vs 20-day avg, signed by price direction
- RSI score: 14-period RSI mapped to oversold(+)/overbought(-) score (regime only)
- Trend score: SMA crossover + MACD histogram combined (regime only)
- Options score: put/call ratio anomaly + IV skew vs baseline
- Earnings surprise: EPS beat/miss with guidance_change and management_tone modifiers
- Analyst score: 30-day LLM-extracted rating changes + price-target upside
- Insider score: 30-day Form 4 net buying, role-weighted, sells discounted
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_SOURCE_CREDIBILITY, SOURCE_CREDIBILITY, settings
from app.models.article import Article, ArticleStock
from app.models.earnings_estimate import EarningsEstimate
from app.models.insider_transaction import InsiderTransaction
from app.models.options_activity import OptionsActivity
from app.models.sentiment import SentimentScore
from worker.utils.article_quality import (
    QUALITY_THRESHOLD,
    SIGNAL_EXCLUDED_SOURCES,
    SIGNAL_MIN_TICKER_CONFIDENCE,
)
from worker.utils.component_math import (
    BASELINE_DAYS,
    PRICE_MOMENTUM_DAYS,
    RSI_LOOKBACK_DAYS,
    TREND_LOOKBACK_DAYS,
    SentimentPoint,
    exp_weighted_sentiment,
    price_momentum,
    rsi_score,
    signed_volume_ratio,
    trend_score,
    volume_anomaly,
)
from worker.utils.market_data_queries import latest_close, recent_close_volume, recent_closes

EARNINGS_WINDOW_DAYS = 2  # Score is active up to 2 days after earnings_date
ANALYST_WINDOW_DAYS = 30
INSIDER_WINDOW_DAYS = 30
INSIDER_NORMALIZATION = 500_000  # $500K → tanh midpoint ≈ 0.76
INSIDER_SELL_DISCOUNT = 0.40  # sells counted at 40% (noise discount)
DEFAULT_ROLE_WEIGHT = 0.8

TONE_BOOST = {
    "confident": 0.10,
    "cautious": -0.10,
    "neutral": 0.0,
}

RATING_WEIGHTS = {
    "upgrade": 1.0,
    "initiate": 0.7,
    "downgrade": -1.0,
    "reiterate": 0.0,
    "maintain": 0.0,
    "none": 0.0,
}


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
        .join(
            ArticleStock,
            (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
        .where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
        .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
        .where(
            (Article.quality_score >= QUALITY_THRESHOLD)
            | (Article.quality_score.is_(None))
        )
        .where(Article.canonical_article_id.is_(None))
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

    points = [
        SentimentPoint(
            value=float(row.positive_score) - float(row.negative_score),
            hours_ago=(now - row.processed_at).total_seconds() / 3600,
            weight=credibility,
        )
        for row, credibility in deduped_rows
    ]
    return exp_weighted_sentiment(points)


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
        .join(
            ArticleStock,
            (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since_24h)
        .where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
        .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
        .where(
            (Article.quality_score >= QUALITY_THRESHOLD)
            | (Article.quality_score.is_(None))
        )
        .where(Article.canonical_article_id.is_(None))
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
        .join(
            ArticleStock,
            (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since_20d)
        .where(SentimentScore.processed_at < since_24h)
        .where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
        .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
        .where(
            (Article.quality_score >= QUALITY_THRESHOLD)
            | (Article.quality_score.is_(None))
        )
        .where(Article.canonical_article_id.is_(None))
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
    return signed_volume_ratio(unique_count, baseline_daily_avg, recent_net_sentiment)


async def calc_price_momentum(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """5-day price change, tanh-scaled to [-1, 1]."""
    closes = await recent_closes(session, stock_id, PRICE_MOMENTUM_DAYS + 1)
    return price_momentum(closes)


async def calc_volume_anomaly(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Trading volume vs 20-day average, signed by price direction."""
    closes, volumes = await recent_close_volume(session, stock_id, BASELINE_DAYS + 1)
    return volume_anomaly(closes, volumes)


async def calc_rsi_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """RSI-based score: oversold (<30) -> positive, overbought (>70) -> negative."""
    closes = await recent_closes(session, stock_id, RSI_LOOKBACK_DAYS)
    return rsi_score(closes)


async def calc_trend_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Combined SMA crossover + MACD crossover trend score."""
    closes = await recent_closes(session, stock_id, TREND_LOOKBACK_DAYS)
    return trend_score(closes)


async def calc_options_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Options flow score from put/call ratio anomaly + IV skew vs baseline.

    Returns positive for bullish options flow (unusual call activity),
    negative for bearish (unusual put activity). Bounded to [-1, 1].
    Returns None if options data is unavailable or insufficient baseline.
    """
    if not settings.options_flow_enabled:
        return None

    today = now.date() if hasattr(now, "date") else now

    # Fetch latest options activity for this stock
    latest_result = await session.execute(
        select(OptionsActivity)
        .where(OptionsActivity.stock_id == stock_id)
        .where(OptionsActivity.date <= today)
        .order_by(OptionsActivity.date.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    if latest is None or latest.data_quality == "stale":
        return None

    # Fetch baseline (last N days)
    baseline_days = settings.options_baseline_days
    baseline_result = await session.execute(
        select(OptionsActivity.put_call_ratio, OptionsActivity.iv_skew)
        .where(OptionsActivity.stock_id == stock_id)
        .where(OptionsActivity.date < latest.date)
        .where(OptionsActivity.data_quality != "stale")
        .order_by(OptionsActivity.date.desc())
        .limit(baseline_days)
    )
    baseline_rows = baseline_result.all()

    if len(baseline_rows) < 5:
        return None  # Cold start — insufficient baseline

    # Put/Call Ratio Anomaly (60%)
    pcr_score = 0.0
    if latest.put_call_ratio is not None:
        pcr_values = [float(r.put_call_ratio) for r in baseline_rows if r.put_call_ratio is not None]
        if len(pcr_values) >= 3:
            pcr_mean = sum(pcr_values) / len(pcr_values)
            pcr_std = (sum((v - pcr_mean) ** 2 for v in pcr_values) / len(pcr_values)) ** 0.5
            pcr_z = (float(latest.put_call_ratio) - pcr_mean) / max(pcr_std, 0.01)
            pcr_score = -math.tanh(pcr_z)  # High P/C = bearish = negative

    # IV Skew Signal (40%)
    skew_score = 0.0
    if latest.iv_skew is not None:
        skew_values = [float(r.iv_skew) for r in baseline_rows if r.iv_skew is not None]
        if len(skew_values) >= 3:
            skew_mean = sum(skew_values) / len(skew_values)
            skew_std = (sum((v - skew_mean) ** 2 for v in skew_values) / len(skew_values)) ** 0.5
            skew_z = (float(latest.iv_skew) - skew_mean) / max(skew_std, 0.01)
            skew_score = -math.tanh(skew_z)  # Widening skew = more expensive puts = bearish

    return 0.6 * pcr_score + 0.4 * skew_score


async def get_recent_article_count(
    session: AsyncSession, stock_id: int, now: datetime
) -> int:
    """Count unique events (deduplicated by duplicate_group_id) in the last 24h."""
    since = now - timedelta(hours=24)
    result = await session.execute(
        select(Article.duplicate_group_id)
        .join(SentimentScore, SentimentScore.article_id == Article.id)
        .join(
            ArticleStock,
            (ArticleStock.article_id == Article.id) & (ArticleStock.stock_id == stock_id),
        )
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
        .where(ArticleStock.confidence >= SIGNAL_MIN_TICKER_CONFIDENCE)
        .where(Article.source.notin_(SIGNAL_EXCLUDED_SOURCES))
        .where(
            (Article.quality_score >= QUALITY_THRESHOLD)
            | (Article.quality_score.is_(None))
        )
        .where(Article.canonical_article_id.is_(None))
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


async def calc_retail_sentiment_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Exponentially weighted sentiment from Reddit-only articles.

    Tracks retail investor sentiment separately from institutional signal scoring.
    Uses the same decay as calc_sentiment_momentum but with no quality gate —
    we want all retail opinion, not just high-quality articles.

    Returns value in [-1, 1] or None if no Reddit articles exist in window.
    """
    since = now - timedelta(hours=48)
    result = await session.execute(
        select(
            SentimentScore.positive_score,
            SentimentScore.negative_score,
            SentimentScore.processed_at,
        )
        .join(Article, SentimentScore.article_id == Article.id)
        .where(SentimentScore.stock_id == stock_id)
        .where(SentimentScore.processed_at >= since)
        .where(Article.source.in_(SIGNAL_EXCLUDED_SOURCES))
    )
    rows = result.all()

    if not rows:
        return None

    points = [
        SentimentPoint(
            value=float(row.positive_score) - float(row.negative_score),
            hours_ago=(now - row.processed_at).total_seconds() / 3600,
            weight=1.0,
        )
        for row in rows
    ]
    return exp_weighted_sentiment(points)


async def calc_earnings_surprise_score(
    session: AsyncSession, stock_id: int, now: datetime
) -> float | None:
    """Earnings surprise score based on EPS beat/miss vs analyst consensus.

    Active only within EARNINGS_WINDOW_DAYS after earnings are reported.
    Returns None outside this window — the composite weight redistributes.

    Score formula:
      base = tanh(surprise_pct / 5.0)
      where surprise_pct is percentage (15.2 = 15.2% beat)

    tanh scaling: ±5% surprise → ±0.46, ±10% → ±0.76, ±15%+ → ~±0.91
    Result is bounded to [-1.0, 1.0].

    LLM modifiers (Phase 21d/21g):
      guidance_change on EarningsEstimate: raised +0.2, lowered -0.2
      management_tone on the latest extracted earnings article: confident +0.10, cautious -0.10
    """
    today = now.date() if hasattr(now, "date") else now

    result = await session.execute(
        select(EarningsEstimate)
        .where(EarningsEstimate.stock_id == stock_id)
        .where(EarningsEstimate.reported == True)  # noqa: E712
        .where(EarningsEstimate.surprise_pct.isnot(None))
        .where(EarningsEstimate.earnings_date >= today - timedelta(days=EARNINGS_WINDOW_DAYS))
        .where(EarningsEstimate.earnings_date <= today)
        .order_by(EarningsEstimate.earnings_date.desc())
        .limit(1)
    )
    earnings = result.scalar_one_or_none()

    if earnings is None:
        return None

    base = math.tanh(float(earnings.surprise_pct) / 5.0)

    guidance_boost = {
        "raised": 0.2,
        "lowered": -0.2,
        "maintained": 0.0,
        None: 0.0,
    }.get(earnings.guidance_change, 0.0)

    tone_boost = await _management_tone_boost(session, stock_id, now)

    return max(-1.0, min(1.0, base + guidance_boost + tone_boost))


async def _management_tone_boost(session: AsyncSession, stock_id: int, now: datetime) -> float:
    """±0.10 from the most recent LLM-extracted earnings article in the window."""
    since = now - timedelta(days=EARNINGS_WINDOW_DAYS)
    result = await session.execute(
        select(Article.metadata_)
        .join(ArticleStock, ArticleStock.article_id == Article.id)
        .where(ArticleStock.stock_id == stock_id)
        .where(Article.event_category == "earnings")
        .where(Article.llm_extracted.is_(True))
        .where(Article.published_at >= since)
        .order_by(Article.published_at.desc())
        .limit(1)
    )
    meta = result.scalar_one_or_none()
    if not isinstance(meta, dict):
        return 0.0
    return TONE_BOOST.get(meta.get("management_tone"), 0.0)


async def calc_analyst_score(session: AsyncSession, stock_id: int, now: datetime) -> float | None:
    """Gated 30-day analyst score from LLM-extracted rating changes and price targets.

    Returns None when no article in the window has a non-zero rating weight
    (upgrade / initiate / downgrade), so the composite redistributes that weight.
    """
    since = now - timedelta(days=ANALYST_WINDOW_DAYS)
    result = await session.execute(
        select(Article.metadata_)
        .join(ArticleStock, ArticleStock.article_id == Article.id)
        .where(ArticleStock.stock_id == stock_id)
        .where(Article.event_category == "analyst_rating")
        .where(Article.llm_extracted.is_(True))
        .where(Article.published_at >= since)
        .where(Article.metadata_.isnot(None))
        .where(Article.metadata_.op("?")("rating_change"))
    )
    rows = result.scalars().all()

    rating_weights: list[float] = []
    price_targets: list[float] = []
    for meta in rows:
        if not isinstance(meta, dict):
            continue
        weight = RATING_WEIGHTS.get(meta.get("rating_change"), 0.0)
        if weight != 0.0:
            rating_weights.append(weight)
        raw_target = meta.get("price_target")
        if raw_target is not None:
            try:
                price_targets.append(float(raw_target))
            except (TypeError, ValueError):
                pass

    if not rating_weights:
        return None

    net_rating_score = math.tanh(sum(rating_weights) / 2.0)

    current_close = await latest_close(session, stock_id) or 0.0

    upside_values = [(pt - current_close) / current_close for pt in price_targets] if current_close > 0 else []
    if upside_values:
        upside_score = math.tanh(sum(upside_values) / len(upside_values) * 5.0)
        return 0.6 * net_rating_score + 0.4 * upside_score
    return net_rating_score


def _insider_role_weight(title: str) -> float:
    """Substring match on insider title. More specific titles win."""
    t = (title or "").lower()
    if "10%" in t or "10 percent" in t or "10-percent" in t:
        return 1.5
    if "ceo" in t or "chief executive" in t:
        return 1.5
    if "cfo" in t or "chief financial" in t:
        return 1.5
    if "coo" in t or "chief operating" in t:
        return 1.5
    if "vice president" in t:
        return 1.0
    if "president" in t:
        return 1.5
    if "director" in t:
        return 1.2
    if "evp" in t or "executive vice" in t:
        return 1.2
    if "svp" in t or "senior vice" in t:
        return 1.1
    if "vp" in t:
        return 1.0
    return DEFAULT_ROLE_WEIGHT


def score_insider_rows(rows) -> float | None:
    """Net signed insider buying from P/S rows. None when the window is empty."""
    if not rows:
        return None
    net_value = 0.0
    for row in rows:
        role_w = _insider_role_weight(getattr(row, "insider_title", None) or "")
        val = float(getattr(row, "transaction_value", None) or 0)
        tx = getattr(row, "transaction_type", None)
        if tx == "P":
            net_value += val * role_w
        elif tx == "S":
            net_value -= val * role_w * INSIDER_SELL_DISCOUNT
    return math.tanh(net_value / INSIDER_NORMALIZATION)


async def calc_insider_score(session: AsyncSession, stock_id: int, as_of_date: datetime) -> float | None:
    """Net signed insider buying over INSIDER_WINDOW_DAYS.

    Buys contribute at full role weight, sells at INSIDER_SELL_DISCOUNT.
    Returns None (gate inactive) when the feature is off or no P/S rows exist.
    """
    if not settings.insider_flow_enabled:
        return None

    as_of = as_of_date.date() if hasattr(as_of_date, "date") else as_of_date
    cutoff = as_of - timedelta(days=INSIDER_WINDOW_DAYS)
    result = await session.execute(
        select(InsiderTransaction)
        .where(InsiderTransaction.stock_id == stock_id)
        .where(InsiderTransaction.transaction_date >= cutoff)
        .where(InsiderTransaction.transaction_date <= as_of)
        .where(InsiderTransaction.transaction_type.in_(["P", "S"]))
    )
    rows = result.scalars().all()
    return score_insider_rows(rows)


