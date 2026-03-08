"""Admin-only endpoints for system management."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.audit import record_audit
from app.core.cache import cached
from app.dependencies import get_current_admin, get_db
from app.models.audit_log import AuditLog
from app.models.task_failure import TaskFailure
from app.models.user import User
from app.schemas.admin import (
    AuditLogResponse,
    PaginatedAuditLogs,
    PaginatedTaskFailures,
    TaskFailureResponse,
)
from app.schemas.common import PaginationMeta, PaginationParams, calc_total_pages, get_total_count
from app.schemas.ml_model import MLModelStatusResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed-history")
async def trigger_historical_seed(
    request: Request,
    period: str = Query("max", description="yfinance period: 1y, 2y, 5y, 10y, max"),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger historical market data backfill as a background Celery task."""
    from worker.tasks.scraping.market_data import seed_historical_market_data

    task = seed_historical_market_data.delay(period)
    await record_audit(db, _admin.id, "seed_history", "admin/seed-history", {"period": period}, request.client.host if request.client else None)
    return {"task_id": task.id, "period": period, "status": "queued"}


@router.post("/scrape-now")
async def trigger_scrape(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate scrape orchestration as a background Celery task."""
    from worker.tasks.scraping.orchestrate import orchestrate_scraping

    task = orchestrate_scraping.delay()
    await record_audit(db, _admin.id, "trigger_scrape", "admin/scrape-now", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/maintenance")
async def trigger_maintenance(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger all data maintenance tasks as a background Celery task."""
    from worker.tasks.maintenance.tasks import run_all_maintenance

    task = run_all_maintenance.delay()
    await record_audit(db, _admin.id, "trigger_maintenance", "admin/maintenance", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/evaluate-outcomes")
async def trigger_outcome_evaluation(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger signal outcome evaluation as a background Celery task."""
    from worker.tasks.signals.outcome_evaluator import evaluate_signal_outcomes

    task = evaluate_signal_outcomes.delay()
    await record_audit(db, _admin.id, "evaluate_outcomes", "admin/evaluate-outcomes", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/compute-weights")
async def trigger_weight_computation(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger adaptive weight computation as a background Celery task."""
    from worker.tasks.signals.weight_optimizer import compute_adaptive_weights

    task = compute_adaptive_weights.delay()
    await record_audit(db, _admin.id, "compute_weights", "admin/compute-weights", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/backfill-event-categories")
async def trigger_backfill_event_categories(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Classify articles that have no event_category set."""
    from worker.tasks.maintenance.tasks import backfill_event_categories

    task = backfill_event_categories.delay()
    await record_audit(db, _admin.id, "backfill_events", "admin/backfill-event-categories", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/backfill-duplicate-groups")
async def trigger_backfill_duplicate_groups(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Detect duplicate articles from the last N days."""
    from worker.tasks.maintenance.tasks import backfill_duplicate_groups

    task = backfill_duplicate_groups.delay(days)
    await record_audit(db, _admin.id, "backfill_duplicates", "admin/backfill-duplicate-groups", {"days": days}, request.client.host if request.client else None)
    return {"task_id": task.id, "days": days, "status": "queued"}


@router.post("/fetch-options")
async def trigger_options_fetch(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger options data fetch as a background Celery task."""
    from worker.tasks.scraping.options_data import fetch_all_options_data

    task = fetch_all_options_data.delay()
    await record_audit(db, _admin.id, "fetch_options", "admin/fetch-options", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.post("/train-ml-models")
async def trigger_ml_training(
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger ML model training as a background Celery task."""
    from worker.tasks.signals.ml_trainer_task import train_ml_models

    task = train_ml_models.delay()
    await record_audit(db, _admin.id, "train_ml_models", "admin/train-ml-models", ip_address=request.client.host if request.client else None)
    return {"task_id": task.id, "status": "queued"}


@router.get("/ml-models", response_model=list[MLModelStatusResponse])
async def get_ml_model_status(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get status of all trained ML models."""
    from app.models.ml_model import MLModel

    result = await db.execute(
        select(MLModel)
        .options(joinedload(MLModel.sector))
        .order_by(MLModel.sector_id.asc().nullsfirst())
    )
    models = result.unique().scalars().all()

    return [
        MLModelStatusResponse(
            sector_name=m.sector.name if m.sector else None,
            model_version=m.model_version,
            training_samples=m.training_samples,
            validation_accuracy=float(m.validation_accuracy) if m.validation_accuracy else None,
            validation_f1=float(m.validation_f1) if m.validation_f1 else None,
            is_active=m.is_active,
            trained_at=m.trained_at,
            feature_importances=json.loads(m.feature_importances) if m.feature_importances else None,
        )
        for m in models
    ]


@router.get("/db-stats")
@cached("admin:db-stats", ttl=300)
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


# ── Task Failures (Dead Letter Queue) ──────────────────────────────


@router.get("/task-failures", response_model=PaginatedTaskFailures)
async def get_task_failures(
    task_name: str | None = Query(None, description="Filter by task name"),
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List task failures (dead letter queue), paginated."""
    query = select(TaskFailure).order_by(TaskFailure.failed_at.desc())
    if task_name:
        query = query.where(TaskFailure.task_name.ilike(f"%{task_name}%"))

    total = await get_total_count(db, query)
    result = await db.execute(query.offset(pagination.offset).limit(pagination.per_page))
    rows = result.scalars().all()

    return PaginatedTaskFailures(
        data=[TaskFailureResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )


@router.post("/task-failures/{failure_id}/retry")
async def retry_failed_task(
    failure_id: int,
    request: Request,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Re-queue a failed task via Celery."""
    result = await db.execute(select(TaskFailure).where(TaskFailure.id == failure_id))
    failure = result.scalar_one_or_none()
    if not failure:
        raise HTTPException(status_code=404, detail="Task failure not found")

    if failure.retried_at:
        raise HTTPException(status_code=409, detail="Already retried")

    import json as json_lib

    args = json_lib.loads(failure.task_args) if failure.task_args else []
    kwargs = json_lib.loads(failure.task_kwargs) if failure.task_kwargs else {}

    from worker.celery_app import celery_app as celery

    task_result = celery.send_task(failure.task_name, args=args, kwargs=kwargs)

    failure.retried_at = datetime.now(timezone.utc)
    failure.retry_task_id = task_result.id
    await record_audit(db, _admin.id, "retry_task", "admin/task-failures/retry", {"failure_id": failure_id, "task_name": failure.task_name}, request.client.host if request.client else None)
    await db.commit()

    return {"task_id": task_result.id, "status": "queued"}


# ── Audit Logs ──────────────────────────────────────────────────────


@router.get("/audit-log", response_model=PaginatedAuditLogs)
async def get_audit_log(
    action: str | None = Query(None, description="Filter by action"),
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List audit log entries, paginated."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)

    total = await get_total_count(db, query)
    result = await db.execute(query.offset(pagination.offset).limit(pagination.per_page))
    rows = result.scalars().all()

    return PaginatedAuditLogs(
        data=[AuditLogResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(
            page=pagination.page,
            per_page=pagination.per_page,
            total=total,
            total_pages=calc_total_pages(total, pagination.per_page),
        ),
    )
