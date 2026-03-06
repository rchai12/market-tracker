from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, get_db
from app.models.sector import Sector
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import PaginationMeta, calc_total_pages
from app.schemas.stock import PaginatedStocks, StockDetailResponse, StockResponse

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/sectors", response_model=list[str])
async def list_sectors(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active sector names."""
    result = await db.execute(
        select(Sector.name).where(Sector.is_active == True).order_by(Sector.name)  # noqa: E712
    )
    return result.scalars().all()


@router.get("", response_model=PaginatedStocks)
async def list_stocks(
    sector: str | None = Query(None, description="Filter by sector name"),
    search: str | None = Query(None, description="Search by ticker or company name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Stock).options(joinedload(Stock.sector))

    if sector:
        query = query.join(Sector).where(func.lower(Sector.name) == sector.lower())

    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Stock.ticker.ilike(pattern)) | (Stock.company_name.ilike(pattern))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Stock.ticker).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    stocks = result.unique().scalars().all()

    data = []
    for stock in stocks:
        resp = StockResponse.model_validate(stock)
        resp.sector_name = stock.sector.name if stock.sector else None
        data.append(resp)

    return PaginatedStocks(
        data=data,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=calc_total_pages(total, per_page),
        ),
    )


@router.get("/{ticker}", response_model=StockDetailResponse)
async def get_stock(
    ticker: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Stock).options(joinedload(Stock.sector)).where(func.upper(Stock.ticker) == ticker.upper())
    )
    stock = result.unique().scalar_one_or_none()

    if not stock:
        raise NotFoundError(f"Stock {ticker} not found")

    resp = StockDetailResponse.model_validate(stock)
    resp.sector_name = stock.sector.name if stock.sector else None
    # latest_sentiment and latest_signal will be populated in Phase 5/6
    return resp
