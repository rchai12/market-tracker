from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.alerts import router as alerts_router
from app.api.api_keys import router as api_keys_router
from app.api.backtests import router as backtests_router
from app.api.articles import router as articles_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.market_data import router as market_data_router
from app.api.sentiment import router as sentiment_router
from app.api.signal_accuracy import router as signal_accuracy_router
from app.api.signals import router as signals_router
from app.api.stocks import router as stocks_router
from app.api.watchlist import router as watchlist_router

router = APIRouter(prefix="/api")

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(api_keys_router)
router.include_router(stocks_router)
router.include_router(watchlist_router)
router.include_router(market_data_router)
router.include_router(articles_router)
router.include_router(sentiment_router)
router.include_router(signal_accuracy_router)
router.include_router(signals_router)
router.include_router(alerts_router)
router.include_router(backtests_router)
router.include_router(admin_router)
