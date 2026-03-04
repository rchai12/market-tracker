from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.articles import router as articles_router
from app.api.auth import router as auth_router
from app.api.market_data import router as market_data_router
from app.api.stocks import router as stocks_router
from app.api.watchlist import router as watchlist_router

router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(stocks_router)
router.include_router(watchlist_router)
router.include_router(market_data_router)
router.include_router(articles_router)
router.include_router(admin_router)


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "stock-predictor"}
