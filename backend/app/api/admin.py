"""Admin-only endpoints for system management."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin, get_db
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


@router.post("/maintenance")
async def trigger_maintenance(
    _admin: User = Depends(get_current_admin),
):
    """Trigger all data maintenance tasks as a background Celery task."""
    from worker.tasks.maintenance.tasks import run_all_maintenance

    task = run_all_maintenance.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/evaluate-outcomes")
async def trigger_outcome_evaluation(
    _admin: User = Depends(get_current_admin),
):
    """Trigger signal outcome evaluation as a background Celery task."""
    from worker.tasks.signals.outcome_evaluator import evaluate_signal_outcomes

    task = evaluate_signal_outcomes.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/compute-weights")
async def trigger_weight_computation(
    _admin: User = Depends(get_current_admin),
):
    """Trigger adaptive weight computation as a background Celery task."""
    from worker.tasks.signals.weight_optimizer import compute_adaptive_weights

    task = compute_adaptive_weights.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/backfill-event-categories")
async def trigger_backfill_event_categories(
    _admin: User = Depends(get_current_admin),
):
    """Classify articles that have no event_category set."""
    from worker.tasks.maintenance.tasks import backfill_event_categories

    task = backfill_event_categories.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/backfill-duplicate-groups")
async def trigger_backfill_duplicate_groups(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    _admin: User = Depends(get_current_admin),
):
    """Detect duplicate articles from the last N days."""
    from worker.tasks.maintenance.tasks import backfill_duplicate_groups

    task = backfill_duplicate_groups.delay(days)
    return {"task_id": task.id, "days": days, "status": "queued"}


@router.get("/db-stats")
async def get_db_stats(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get row counts and estimated sizes for all tables.

    Uses Postgres stats catalog — no full table scans.
    """
    result = await db.execute(text("""
        SELECT
            relname AS table_name,
            n_live_tup AS estimated_rows,
            pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
            pg_total_relation_size(relid) AS total_size_bytes
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(relid) DESC
    """))
    rows = result.all()

    tables = [
        {
            "table": row.table_name,
            "estimated_rows": row.estimated_rows,
            "total_size": row.total_size,
            "total_size_bytes": row.total_size_bytes,
        }
        for row in rows
    ]
    total_bytes = sum(t["total_size_bytes"] for t in tables)

    return {
        "tables": tables,
        "total_size": f"{total_bytes / (1024 * 1024):.1f} MB",
        "total_size_bytes": total_bytes,
    }
