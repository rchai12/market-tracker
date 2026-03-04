"""Alert configuration and history API endpoints."""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.dependencies import get_current_user, get_db
from app.models.alert import AlertConfig, AlertLog
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.schemas.signal import (
    AlertConfigCreate,
    AlertConfigResponse,
    AlertConfigUpdate,
    AlertLogResponse,
    PaginatedAlertLogs,
    PaginationMeta,
    TestAlertRequest,
    TestAlertResponse,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ── AlertConfig CRUD ──


@router.get("/configs", response_model=list[AlertConfigResponse])
async def get_alert_configs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all alert configurations for the current user."""
    result = await db.execute(
        select(AlertConfig)
        .where(AlertConfig.user_id == user.id)
        .order_by(AlertConfig.created_at.desc())
    )
    configs = result.scalars().all()

    stock_ids = [c.stock_id for c in configs if c.stock_id is not None]
    ticker_map = {}
    if stock_ids:
        stock_result = await db.execute(
            select(Stock.id, Stock.ticker).where(Stock.id.in_(stock_ids))
        )
        ticker_map = {row.id: row.ticker for row in stock_result.all()}

    return [
        AlertConfigResponse(
            id=c.id,
            user_id=c.user_id,
            stock_id=c.stock_id,
            ticker=ticker_map.get(c.stock_id) if c.stock_id else None,
            min_strength=c.min_strength,
            direction_filter=c.direction_filter,
            channel=c.channel,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in configs
    ]


@router.post("/configs", response_model=AlertConfigResponse, status_code=201)
async def create_alert_config(
    body: AlertConfigCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert configuration."""
    ticker = None
    if body.stock_id is not None:
        stock_result = await db.execute(
            select(Stock).where(Stock.id == body.stock_id)
        )
        stock = stock_result.scalar_one_or_none()
        if not stock:
            raise NotFoundError(f"Stock with id {body.stock_id} not found")
        ticker = stock.ticker

    config = AlertConfig(
        user_id=user.id,
        stock_id=body.stock_id,
        min_strength=body.min_strength,
        direction_filter=body.direction_filter,
        channel=body.channel,
    )
    db.add(config)
    await db.flush()

    return AlertConfigResponse(
        id=config.id,
        user_id=config.user_id,
        stock_id=config.stock_id,
        ticker=ticker,
        min_strength=config.min_strength,
        direction_filter=config.direction_filter,
        channel=config.channel,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.put("/configs/{config_id}", response_model=AlertConfigResponse)
async def update_alert_config(
    config_id: int,
    body: AlertConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an alert configuration. Only the owner can update."""
    result = await db.execute(
        select(AlertConfig).where(AlertConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("Alert config not found")
    if config.user_id != user.id:
        raise ForbiddenError("Not your alert config")

    if body.stock_id is not None:
        config.stock_id = body.stock_id
    if body.min_strength is not None:
        config.min_strength = body.min_strength
    if body.direction_filter is not None:
        config.direction_filter = body.direction_filter
    if body.channel is not None:
        config.channel = body.channel
    if body.is_active is not None:
        config.is_active = body.is_active

    await db.flush()

    ticker = None
    if config.stock_id:
        stock_result = await db.execute(
            select(Stock.ticker).where(Stock.id == config.stock_id)
        )
        ticker = stock_result.scalar_one_or_none()

    return AlertConfigResponse(
        id=config.id,
        user_id=config.user_id,
        stock_id=config.stock_id,
        ticker=ticker,
        min_strength=config.min_strength,
        direction_filter=config.direction_filter,
        channel=config.channel,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.delete("/configs/{config_id}", status_code=204)
async def delete_alert_config(
    config_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert configuration."""
    result = await db.execute(
        select(AlertConfig).where(AlertConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("Alert config not found")
    if config.user_id != user.id:
        raise ForbiddenError("Not your alert config")

    await db.delete(config)


# ── Alert History ──


@router.get("/history", response_model=PaginatedAlertLogs)
async def get_alert_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sent alert log for the current user."""
    base_query = select(AlertLog).where(AlertLog.user_id == user.id)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        base_query
        .options(joinedload(AlertLog.signal).joinedload(Signal.stock))
        .order_by(AlertLog.sent_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    logs = result.unique().scalars().all()

    data = [
        AlertLogResponse(
            id=log.id,
            signal_id=log.signal_id,
            user_id=log.user_id,
            channel=log.channel,
            sent_at=log.sent_at,
            success=log.success,
            error_message=log.error_message,
            ticker=log.signal.stock.ticker if log.signal and log.signal.stock else None,
            direction=log.signal.direction if log.signal else None,
            strength=log.signal.strength if log.signal else None,
        )
        for log in logs
    ]

    return PaginatedAlertLogs(
        data=data,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=max(1, math.ceil(total / per_page)),
        ),
    )


# ── Test Alert ──


@router.post("/test", response_model=TestAlertResponse)
async def send_test_alert(
    body: TestAlertRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a test alert to verify channel configuration."""
    from worker.tasks.signals.alert_dispatcher import (
        _send_discord_alert,
        _send_email_alert,
    )

    class MockSignal:
        direction = "bullish"
        strength = "moderate"
        composite_score = 0.42
        article_count = 5
        reasoning = "This is a test alert to verify your notification configuration."

        class stock:
            ticker = "TEST"

    mock_signal = MockSignal()
    channels = ["discord", "email"] if body.channel == "both" else [body.channel]
    results = []

    for ch in channels:
        if ch == "discord":
            success, error = await _send_discord_alert(mock_signal, user)
        elif ch == "email":
            success, error = await _send_email_alert(mock_signal, user)
        else:
            success, error = False, f"Unknown channel: {ch}"
        results.append((ch, success, error))

    all_success = all(r[1] for r in results)
    messages = []
    for ch, ok, err in results:
        if ok:
            messages.append(f"{ch}: sent successfully")
        else:
            messages.append(f"{ch}: failed - {err}")

    return TestAlertResponse(
        success=all_success,
        message="; ".join(messages),
    )
