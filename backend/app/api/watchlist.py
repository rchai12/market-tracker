from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.dependencies import get_current_user, get_db
from app.models.sector import Sector
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import WatchlistAdd, WatchlistItemResponse

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemResponse])
async def get_watchlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WatchlistItem)
        .options(joinedload(WatchlistItem.stock).joinedload(Stock.sector))
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.added_at.desc())
    )
    items = result.unique().scalars().all()

    return [
        WatchlistItemResponse(
            id=item.id,
            stock_id=item.stock_id,
            ticker=item.stock.ticker,
            company_name=item.stock.company_name,
            sector_name=item.stock.sector.name if item.stock.sector else None,
            added_at=item.added_at,
        )
        for item in items
    ]


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def add_to_watchlist(
    body: WatchlistAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Find the stock
    result = await db.execute(
        select(Stock).options(joinedload(Stock.sector)).where(func.upper(Stock.ticker) == body.ticker.upper())
    )
    stock = result.unique().scalar_one_or_none()
    if not stock:
        raise NotFoundError(f"Stock {body.ticker} not found")

    # Check if already in watchlist
    existing = await db.execute(
        select(WatchlistItem).where(
            (WatchlistItem.user_id == user.id) & (WatchlistItem.stock_id == stock.id)
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"{body.ticker} is already in your watchlist")

    item = WatchlistItem(user_id=user.id, stock_id=stock.id)
    db.add(item)
    await db.flush()

    return WatchlistItemResponse(
        id=item.id,
        stock_id=stock.id,
        ticker=stock.ticker,
        company_name=stock.company_name,
        sector_name=stock.sector.name if stock.sector else None,
        added_at=item.added_at,
    )


@router.delete("/{ticker}", status_code=204)
async def remove_from_watchlist(
    ticker: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Stock).where(func.upper(Stock.ticker) == ticker.upper())
    )
    stock = result.scalar_one_or_none()
    if not stock:
        raise NotFoundError(f"Stock {ticker} not found")

    result = await db.execute(
        select(WatchlistItem).where(
            (WatchlistItem.user_id == user.id) & (WatchlistItem.stock_id == stock.id)
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError(f"{ticker} is not in your watchlist")

    await db.delete(item)
