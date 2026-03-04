"""Sentiment analysis API endpoints."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_user, get_db, get_stock_by_ticker
from app.models.article import Article, ArticleStock
from app.models.sector import Sector
from app.models.sentiment import SentimentScore
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import PaginationMeta, calc_total_pages
from app.schemas.sentiment import (
    PaginatedSentiment,
    SentimentScoreResponse,
    SentimentSummary,
    SentimentTimePoint,
)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/{ticker}", response_model=list[SentimentTimePoint])
async def get_ticker_sentiment_timeline(
    ticker: str,
    days: int = Query(30, ge=1, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get daily sentiment time series for a ticker."""
    stock = await get_stock_by_ticker(ticker, db)
    since = date.today() - timedelta(days=days)

    query = (
        select(
            cast(SentimentScore.processed_at, Date).label("date"),
            func.avg(SentimentScore.positive_score).label("avg_positive"),
            func.avg(SentimentScore.negative_score).label("avg_negative"),
            func.avg(SentimentScore.neutral_score).label("avg_neutral"),
            func.count(SentimentScore.id).label("article_count"),
        )
        .where(SentimentScore.stock_id == stock.id)
        .where(cast(SentimentScore.processed_at, Date) >= since)
        .group_by(cast(SentimentScore.processed_at, Date))
        .order_by(cast(SentimentScore.processed_at, Date))
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        SentimentTimePoint(
            date=str(row.date),
            avg_positive=round(float(row.avg_positive), 4),
            avg_negative=round(float(row.avg_negative), 4),
            avg_neutral=round(float(row.avg_neutral), 4),
            article_count=row.article_count,
            dominant_label=_dominant_label(float(row.avg_positive), float(row.avg_negative), float(row.avg_neutral)),
        )
        for row in rows
    ]


@router.get("/{ticker}/articles", response_model=PaginatedSentiment)
async def get_ticker_sentiment_articles(
    ticker: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sentiment-scored articles for a specific ticker."""
    stock = await get_stock_by_ticker(ticker, db)

    base_query = select(SentimentScore).where(SentimentScore.stock_id == stock.id)

    # Count
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page with article join
    query = (
        base_query
        .join(Article)
        .options(selectinload(SentimentScore.article))
        .order_by(SentimentScore.processed_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    scores = result.scalars().unique().all()

    data = [
        SentimentScoreResponse(
            id=s.id,
            article_id=s.article_id,
            stock_id=s.stock_id,
            label=s.label,
            positive_score=float(s.positive_score),
            negative_score=float(s.negative_score),
            neutral_score=float(s.neutral_score),
            model_version=s.model_version,
            processed_at=s.processed_at,
            article_title=s.article.title if s.article else None,
            article_source=s.article.source if s.article else None,
        )
        for s in scores
    ]

    return PaginatedSentiment(
        data=data,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=calc_total_pages(total, per_page),
        ),
    )


@router.get("/summary/sectors", response_model=list[SentimentSummary])
async def get_sector_sentiment_summary(
    days: int = Query(7, ge=1, le=90),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated sentiment summary per active sector."""
    since = date.today() - timedelta(days=days)

    query = (
        select(
            Sector.name.label("sector_name"),
            func.count(SentimentScore.id).label("total"),
            func.sum(case((SentimentScore.label == "positive", 1), else_=0)).label("pos_count"),
            func.sum(case((SentimentScore.label == "negative", 1), else_=0)).label("neg_count"),
            func.sum(case((SentimentScore.label == "neutral", 1), else_=0)).label("neu_count"),
            func.avg(SentimentScore.positive_score).label("avg_pos"),
            func.avg(SentimentScore.negative_score).label("avg_neg"),
            func.avg(SentimentScore.neutral_score).label("avg_neu"),
        )
        .join(Stock, SentimentScore.stock_id == Stock.id)
        .join(Sector, Stock.sector_id == Sector.id)
        .where(cast(SentimentScore.processed_at, Date) >= since)
        .where(Sector.is_active == True)  # noqa: E712
        .group_by(Sector.name)
        .order_by(Sector.name)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        SentimentSummary(
            sector=row.sector_name,
            total_articles=row.total,
            positive_count=row.pos_count or 0,
            negative_count=row.neg_count or 0,
            neutral_count=row.neu_count or 0,
            avg_positive=round(float(row.avg_pos or 0), 4),
            avg_negative=round(float(row.avg_neg or 0), 4),
            avg_neutral=round(float(row.avg_neu or 0), 4),
            dominant_label=_dominant_label(
                float(row.avg_pos or 0), float(row.avg_neg or 0), float(row.avg_neu or 0)
            ),
        )
        for row in rows
    ]


@router.get("/trending/stocks", response_model=list[SentimentSummary])
async def get_trending_sentiment(
    days: int = Query(3, ge=1, le=30),
    limit: int = Query(10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get stocks with highest sentiment activity (most scored articles)."""
    since = date.today() - timedelta(days=days)

    query = (
        select(
            Stock.ticker,
            func.count(SentimentScore.id).label("total"),
            func.sum(case((SentimentScore.label == "positive", 1), else_=0)).label("pos_count"),
            func.sum(case((SentimentScore.label == "negative", 1), else_=0)).label("neg_count"),
            func.sum(case((SentimentScore.label == "neutral", 1), else_=0)).label("neu_count"),
            func.avg(SentimentScore.positive_score).label("avg_pos"),
            func.avg(SentimentScore.negative_score).label("avg_neg"),
            func.avg(SentimentScore.neutral_score).label("avg_neu"),
        )
        .join(Stock, SentimentScore.stock_id == Stock.id)
        .where(cast(SentimentScore.processed_at, Date) >= since)
        .where(SentimentScore.stock_id != None)  # noqa: E711
        .group_by(Stock.ticker)
        .order_by(func.count(SentimentScore.id).desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        SentimentSummary(
            ticker=row.ticker,
            total_articles=row.total,
            positive_count=row.pos_count or 0,
            negative_count=row.neg_count or 0,
            neutral_count=row.neu_count or 0,
            avg_positive=round(float(row.avg_pos or 0), 4),
            avg_negative=round(float(row.avg_neg or 0), 4),
            avg_neutral=round(float(row.avg_neu or 0), 4),
            dominant_label=_dominant_label(
                float(row.avg_pos or 0), float(row.avg_neg or 0), float(row.avg_neu or 0)
            ),
        )
        for row in rows
    ]


def _dominant_label(pos: float, neg: float, neu: float) -> str:
    scores = {"positive": pos, "negative": neg, "neutral": neu}
    return max(scores, key=scores.get)
