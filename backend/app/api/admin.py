"""Admin-only endpoints for system management."""

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_admin
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed-history")
async def trigger_historical_seed(
    period: str = Query("max", description="yfinance period: 1y, 2y, 5y, 10y, max"),
    _admin: User = Depends(get_current_admin),
):
    """Trigger historical market data backfill as a background Celery task."""
    from worker.tasks.scraping.market_data import seed_historical_market_data

    task = seed_historical_market_data.delay(period)
    return {"task_id": task.id, "period": period, "status": "queued"}


@router.post("/scrape-now")
async def trigger_scrape(
    _admin: User = Depends(get_current_admin),
):
    """Trigger an immediate scrape orchestration as a background Celery task."""
    from worker.tasks.scraping.orchestrate import orchestrate_scraping

    task = orchestrate_scraping.delay()
    return {"task_id": task.id, "status": "queued"}
