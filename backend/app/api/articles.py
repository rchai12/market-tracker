"""Articles API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_user, get_db
from app.models.article import Article, ArticleStock
from app.models.stock import Stock
from app.models.user import User
from app.schemas.article import ArticleResponse, PaginatedArticles
from app.schemas.common import PaginationMeta, calc_total_pages, get_total_count

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=PaginatedArticles)
async def list_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source: str | None = Query(None, description="Filter by source (yahoo_news, finviz, etc.)"),
    ticker: str | None = Query(None, description="Filter by associated stock ticker"),
    is_processed: bool | None = Query(None, description="Filter by processing status"),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List articles with optional filters and pagination."""
    base_query = select(Article)

    if source:
        base_query = base_query.where(Article.source == source)

    if is_processed is not None:
        base_query = base_query.where(Article.is_processed == is_processed)

    if ticker:
        base_query = base_query.join(ArticleStock).join(Stock).where(
            func.upper(Stock.ticker) == ticker.upper()
        )

    total = await get_total_count(db, base_query)

    # Fetch page
    query = (
        base_query
        .options(selectinload(Article.article_stocks).selectinload(ArticleStock.stock))
        .order_by(Article.scraped_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    articles = result.scalars().unique().all()

    data = []
    for article in articles:
        tickers = [
            as_.stock.ticker
            for as_ in article.article_stocks
            if as_.stock is not None
        ]
        resp = ArticleResponse(
            id=article.id,
            source=article.source,
            source_url=article.source_url,
            title=article.title,
            summary=article.summary,
            author=article.author,
            published_at=article.published_at,
            scraped_at=article.scraped_at,
            is_processed=article.is_processed,
            event_category=article.event_category,
            tickers=tickers,
        )
        data.append(resp)

    return PaginatedArticles(
        data=data,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=calc_total_pages(total, per_page),
        ),
    )


@router.get("/sources")
async def list_sources(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available article sources with counts."""
    query = (
        select(Article.source, func.count(Article.id).label("count"))
        .group_by(Article.source)
        .order_by(func.count(Article.id).desc())
    )
    result = await db.execute(query)
    return [{"source": row.source, "count": row.count} for row in result.all()]
