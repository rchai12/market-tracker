"""Signal API endpoints — core signal CRUD and detail."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.cache import cached
from app.dependencies import get_current_user, get_db, get_stock_by_ticker
from app.models.article import Article
from app.models.daily_signal_view import DailySignalView
from app.models.market_data import MarketDataDaily
from app.models.sector import Sector
from app.models.sentiment import SentimentScore
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import PaginationMeta, PaginationParams, calc_total_pages, get_total_count
from app.schemas.signal import (
    DailySignalViewResponse,
    DailyViewOutcome,
    LinkedArticle,
    PaginatedDailyViews,
    PaginatedSignals,
    SignalDetailResponse,
    SignalOutcomeResponse,
    SignalResponse,
    TodaysPredictionsResponse,
)
from worker.utils.daily_aggregation import trading_date_lower_bound

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/latest", response_model=list[SignalResponse])
async def get_latest_signals(
    limit: int = Query(20, ge=1, le=100),
    min_strength: str | None = Query(None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent signals across all stocks. For dashboard feed."""
    query = (
        select(Signal)
        .options(joinedload(Signal.stock))
        .order_by(Signal.generated_at.desc())
    )

    if min_strength:
        query = query.where(Signal.strength == min_strength)

    query = query.limit(limit)
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return [_to_response(s) for s in signals]


@router.get("/detail/{signal_id}", response_model=SignalDetailResponse)
async def get_signal_detail(
    signal_id: int,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full signal detail with outcomes and linked articles."""
    result = await db.execute(
        select(Signal)
        .options(joinedload(Signal.stock), joinedload(Signal.outcomes))
        .where(Signal.id == signal_id)
    )
    signal = result.unique().scalars().first()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Build outcomes
    outcomes = [
        SignalOutcomeResponse(
            window_days=o.window_days,
            price_change_pct=float(o.price_change_pct),
            is_correct=o.is_correct,
            evaluated_at=o.evaluated_at,
        )
        for o in sorted(signal.outcomes, key=lambda o: o.window_days)
    ]

    # Find linked articles via sentiment_scores in signal's time window
    article_query = (
        select(
            Article.id,
            Article.title,
            Article.source,
            Article.source_url,
            Article.published_at,
            SentimentScore.label,
            (SentimentScore.positive_score - SentimentScore.negative_score).label("net_sentiment"),
        )
        .join(SentimentScore, Article.id == SentimentScore.article_id)
        .where(SentimentScore.stock_id == signal.stock_id)
        .where(SentimentScore.processed_at >= signal.window_start)
        .where(SentimentScore.processed_at <= signal.window_end)
        .order_by(Article.published_at.desc().nullslast())
        .limit(50)
    )
    article_result = await db.execute(article_query)
    article_rows = article_result.all()

    linked_articles = [
        LinkedArticle(
            id=row.id,
            title=row.title,
            source=row.source,
            url=row.source_url,
            published_at=row.published_at,
            sentiment_label=row.label,
            sentiment_score=round(float(row.net_sentiment), 4) if row.net_sentiment is not None else None,
        )
        for row in article_rows
    ]

    return SignalDetailResponse(
        signal=_to_response(signal),
        outcomes=outcomes,
        linked_articles=linked_articles,
    )


@router.get("/daily-views/today", response_model=TodaysPredictionsResponse)
@cached("signals:daily-views-today", ttl=300)
async def get_todays_predictions(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Today's net views for the dashboard. Cached 5 minutes."""
    floor = trading_date_lower_bound(datetime.now(UTC))
    trading = await _resolve_today_trading_date(db, floor)
    if trading is None:
        return TodaysPredictionsResponse(trading_date=floor, data=[])

    query = (
        select(DailySignalView)
        .options(
            joinedload(DailySignalView.stock).joinedload(Stock.sector),
            joinedload(DailySignalView.outcomes),
        )
        .where(DailySignalView.trading_date == trading)
        .order_by(DailySignalView.conviction.desc())
    )
    result = await db.execute(query)
    views = list(result.unique().scalars().all())
    live = await _live_change_map(db, views)
    return TodaysPredictionsResponse(
        trading_date=trading,
        data=[_to_daily_view(v, live.get(v.id)) for v in views],
    )


@router.get("/daily-views", response_model=PaginatedDailyViews)
async def list_daily_views(
    pagination: PaginationParams = Depends(),
    view_date: date | None = Query(None, alias="date"),
    sector: str | None = Query(None),
    direction: str | None = Query(None),
    min_conviction: float | None = Query(None, ge=0.0, le=1.0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated daily net views with optional filters."""
    base_query = select(DailySignalView)
    if view_date is not None:
        base_query = base_query.where(DailySignalView.trading_date == view_date)
    if direction:
        base_query = base_query.where(DailySignalView.direction == direction)
    if min_conviction is not None:
        base_query = base_query.where(DailySignalView.conviction >= min_conviction)
    if sector:
        base_query = (
            base_query.join(Stock, DailySignalView.stock_id == Stock.id)
            .join(Sector, Stock.sector_id == Sector.id)
            .where(func.lower(Sector.name) == sector.lower())
        )

    total = await get_total_count(db, base_query)
    query = (
        base_query.options(
            joinedload(DailySignalView.stock).joinedload(Stock.sector),
            joinedload(DailySignalView.outcomes),
        )
        .order_by(DailySignalView.trading_date.desc(), DailySignalView.conviction.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    result = await db.execute(query)
    views = list(result.unique().scalars().all())
    live = await _live_change_map(db, views)
    return PaginatedDailyViews(
        data=[_to_daily_view(v, live.get(v.id)) for v in views],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )


@router.get("/{ticker}", response_model=PaginatedSignals)
async def get_signal_history(
    ticker: str,
    pagination: PaginationParams = Depends(),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get signal history for a specific ticker."""
    stock = await get_stock_by_ticker(ticker, db)

    base_query = select(Signal).where(Signal.stock_id == stock.id)

    total = await get_total_count(db, base_query)

    query = (
        base_query
        .options(joinedload(Signal.stock))
        .order_by(Signal.generated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return PaginatedSignals(
        data=[_to_response(s) for s in signals],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )


@router.get("", response_model=PaginatedSignals)
async def list_signals(
    pagination: PaginationParams = Depends(),
    direction: str | None = Query(None),
    strength: str | None = Query(None),
    ticker: str | None = Query(None),
    sector: str | None = Query(None, description="Filter by sector name"),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all signals with optional filters and pagination."""
    base_query = select(Signal)

    if direction:
        base_query = base_query.where(Signal.direction == direction)

    if strength:
        base_query = base_query.where(Signal.strength == strength)

    if ticker:
        base_query = base_query.join(Stock).where(
            func.upper(Stock.ticker) == ticker.upper()
        )

    if sector:
        if ticker:
            # Stock already joined
            base_query = base_query.join(Sector).where(func.lower(Sector.name) == sector.lower())
        else:
            base_query = base_query.join(Stock).join(Sector).where(func.lower(Sector.name) == sector.lower())

    total = await get_total_count(db, base_query)

    query = (
        base_query
        .options(joinedload(Signal.stock))
        .order_by(Signal.generated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    result = await db.execute(query)
    signals = result.unique().scalars().all()

    return PaginatedSignals(
        data=[_to_response(s) for s in signals],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )


def _to_response(signal: Signal) -> SignalResponse:
    return SignalResponse(
        id=signal.id,
        stock_id=signal.stock_id,
        ticker=signal.stock.ticker if signal.stock else "???",
        company_name=signal.stock.company_name if signal.stock else "Unknown",
        direction=signal.direction,
        strength=signal.strength,
        composite_score=float(signal.composite_score),
        sentiment_score=_f(signal.sentiment_score),
        sentiment_volume_score=_f(signal.sentiment_volume_score),
        price_score=_f(signal.price_score),
        volume_score=_f(signal.volume_score),
        rsi_score=_f(signal.rsi_score),
        trend_score=_f(signal.trend_score),
        options_score=_f(signal.options_score),
        article_count=signal.article_count,
        reasoning=signal.reasoning,
        ml_score=_f(signal.ml_score),
        ml_direction=signal.ml_direction,
        ml_confidence=_f(signal.ml_confidence),
        has_ml=bool(getattr(signal, "has_ml", False)),
        market_regime=signal.market_regime,
        earnings_score=_f(signal.earnings_score),
        analyst_score=_f(signal.analyst_score),
        insider_score=_f(getattr(signal, "insider_score", None)),
        retail_sentiment_score=_f(signal.retail_sentiment_score),
        generated_at=signal.generated_at,
        window_start=signal.window_start,
        window_end=signal.window_end,
    )


def _f(val) -> float | None:
    """Preserve 0.0; only missing values become None."""
    return float(val) if val is not None else None


def _outcome_window(view: DailySignalView, window_days: int) -> DailyViewOutcome | None:
    for outcome in view.outcomes or []:
        if outcome.window_days == window_days:
            return DailyViewOutcome(
                price_change_pct=float(outcome.price_change_pct),
                is_correct=bool(outcome.is_correct),
            )
    return None


def _to_daily_view(view: DailySignalView, live_change_pct: float | None) -> DailySignalViewResponse:
    stock = view.stock
    sector_name = stock.sector.name if stock and stock.sector else None
    return DailySignalViewResponse(
        ticker=stock.ticker if stock else "???",
        sector=sector_name,
        trading_date=view.trading_date,
        direction=view.direction,
        net_score=float(view.net_score),
        conviction=float(view.conviction),
        signal_count=view.signal_count,
        outcome_1d=_outcome_window(view, 1),
        outcome_3d=_outcome_window(view, 3),
        outcome_5d=_outcome_window(view, 5),
        live_change_pct=live_change_pct,
    )


async def _resolve_today_trading_date(db: AsyncSession, floor: date) -> date | None:
    result = await db.execute(
        select(func.min(DailySignalView.trading_date)).where(DailySignalView.trading_date >= floor)
    )
    found = result.scalar_one_or_none()
    if found is not None:
        return found
    fallback = await db.execute(select(func.max(DailySignalView.trading_date)))
    return fallback.scalar_one_or_none()


async def _live_change_map(db: AsyncSession, views: list[DailySignalView]) -> dict[int, float | None]:
    """Latest close vs close before each view's trading_date."""
    if not views:
        return {}
    stock_ids = {view.stock_id for view in views}
    min_date = min(view.trading_date for view in views) - timedelta(days=14)
    result = await db.execute(
        select(MarketDataDaily.stock_id, MarketDataDaily.date, MarketDataDaily.close)
        .where(MarketDataDaily.stock_id.in_(stock_ids))
        .where(MarketDataDaily.date >= min_date)
        .where(MarketDataDaily.close.isnot(None))
        .order_by(MarketDataDaily.stock_id, MarketDataDaily.date.asc())
    )
    by_stock: dict[int, list[tuple[date, float]]] = {}
    for stock_id, bar_date, close in result.all():
        by_stock.setdefault(stock_id, []).append((bar_date, float(close)))

    live: dict[int, float | None] = {}
    for view in views:
        bars = by_stock.get(view.stock_id, [])
        if not bars:
            live[view.id] = None
            continue
        prev = next((close for bar_date, close in reversed(bars) if bar_date < view.trading_date), None)
        latest = bars[-1][1]
        if prev is None or prev == 0:
            live[view.id] = None
            continue
        live[view.id] = (latest - prev) / prev
    return live
