"""Daily-view accuracy observability endpoints (Phase 24c)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cached
from app.dependencies import get_current_user, get_db
from app.models.daily_signal_view import DailySignalView, DailySignalViewOutcome
from app.models.sector import Sector
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.schemas.signal import (
    DailyViewAccuracySummary,
    DailyViewAccuracyTrendResponse,
    DailyViewCalibrationResponse,
    DailyViewRegimeAccuracyResponse,
    DailyViewSectorAccuracyResponse,
)
from worker.utils.daily_accuracy import (
    DEFAULT_MIN_CONVICTION,
    AccuracyRow,
    aggregate_by_label,
    aggregate_calibration,
    aggregate_weekly_trend,
    summarize_accuracy,
)

router = APIRouter(prefix="/signals", tags=["signals"])


def _apply_view_filters(
    query,
    *,
    sector: str | None,
    direction: str | None,
    date_from: date | None,
    date_to: date | None,
    min_conviction: float,
):
    query = query.where(DailySignalView.conviction >= min_conviction)
    query = query.where(DailySignalView.direction.in_(["bullish", "bearish"]))
    if direction:
        query = query.where(DailySignalView.direction == direction)
    if date_from is not None:
        query = query.where(DailySignalView.trading_date >= date_from)
    if date_to is not None:
        query = query.where(DailySignalView.trading_date <= date_to)
    if sector:
        query = query.where(func.lower(Sector.name) == sector.lower())
    return query


def _outcome_join(window_days: int, evaluated_only: bool) -> tuple[object, bool]:
    onclause = (DailySignalViewOutcome.daily_view_id == DailySignalView.id) & (
        DailySignalViewOutcome.window_days == window_days
    )
    return onclause, evaluated_only


def _base_select(window_days: int, evaluated_only: bool):
    stmt = select(
        DailySignalView.conviction,
        DailySignalViewOutcome.is_correct,
        DailySignalViewOutcome.excess_return_pct,
        DailySignalViewOutcome.price_change_pct,
        DailySignalView.trading_date,
        Sector.name,
    ).select_from(DailySignalView)
    onclause, inner = _outcome_join(window_days, evaluated_only)
    if inner:
        stmt = stmt.join(DailySignalViewOutcome, onclause)
    else:
        stmt = stmt.outerjoin(DailySignalViewOutcome, onclause)
    stmt = stmt.join(Stock, DailySignalView.stock_id == Stock.id)
    stmt = stmt.join(Sector, Stock.sector_id == Sector.id)
    return stmt


def _row_from_sql(row) -> AccuracyRow:
    excess = row.excess_return_pct if row.excess_return_pct is not None else row.price_change_pct
    return AccuracyRow(
        conviction=float(row.conviction),
        is_correct=None if row.is_correct is None else bool(row.is_correct),
        excess_return=None if excess is None else float(excess),
        trading_date=row.trading_date,
        sector=row.name,
    )


async def _fetch_rows(
    db: AsyncSession,
    *,
    window_days: int,
    sector: str | None,
    direction: str | None,
    date_from: date | None,
    date_to: date | None,
    min_conviction: float,
    evaluated_only: bool = True,
) -> list[AccuracyRow]:
    stmt = _apply_view_filters(
        _base_select(window_days, evaluated_only),
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
    )
    result = await db.execute(stmt)
    return [_row_from_sql(row) for row in result.all()]


def _query_kwargs():
    return dict(
        window_days=Query(1, ge=1, le=30),
        sector=Query(None),
        direction=Query(None),
        date_from=Query(None),
        date_to=Query(None),
        min_conviction=Query(DEFAULT_MIN_CONVICTION, ge=0.0, le=1.0),
    )


@router.get("/daily-views/accuracy", response_model=DailyViewAccuracySummary)
@cached("signals:daily-accuracy:summary", ttl=300)
async def get_daily_view_accuracy(
    window_days: int = Query(1, ge=1, le=30),
    sector: str | None = Query(None),
    direction: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    min_conviction: float = Query(DEFAULT_MIN_CONVICTION, ge=0.0, le=1.0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Headline daily-view accuracy (same `is_correct` the learning loop uses)."""
    rows = await _fetch_rows(
        db,
        window_days=window_days,
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
        evaluated_only=False,
    )
    return DailyViewAccuracySummary(**summarize_accuracy(rows))


@router.get("/daily-views/accuracy/trend", response_model=DailyViewAccuracyTrendResponse)
@cached("signals:daily-accuracy:trend", ttl=300)
async def get_daily_view_accuracy_trend(
    window_days: int = Query(1, ge=1, le=30),
    sector: str | None = Query(None),
    direction: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    min_conviction: float = Query(DEFAULT_MIN_CONVICTION, ge=0.0, le=1.0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await _fetch_rows(
        db,
        window_days=window_days,
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
    )
    return DailyViewAccuracyTrendResponse(buckets=aggregate_weekly_trend(rows))


@router.get("/daily-views/accuracy/calibration", response_model=DailyViewCalibrationResponse)
@cached("signals:daily-accuracy:calibration", ttl=300)
async def get_daily_view_accuracy_calibration(
    window_days: int = Query(1, ge=1, le=30),
    sector: str | None = Query(None),
    direction: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    min_conviction: float = Query(DEFAULT_MIN_CONVICTION, ge=0.0, le=1.0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await _fetch_rows(
        db,
        window_days=window_days,
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
    )
    return DailyViewCalibrationResponse(buckets=aggregate_calibration(rows))


@router.get("/daily-views/accuracy/sectors", response_model=DailyViewSectorAccuracyResponse)
@cached("signals:daily-accuracy:sectors", ttl=300)
async def get_daily_view_accuracy_sectors(
    window_days: int = Query(1, ge=1, le=30),
    sector: str | None = Query(None),
    direction: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    min_conviction: float = Query(DEFAULT_MIN_CONVICTION, ge=0.0, le=1.0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await _fetch_rows(
        db,
        window_days=window_days,
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
    )
    return DailyViewSectorAccuracyResponse(sectors=aggregate_by_label(rows, "sector"))


@router.get("/daily-views/accuracy/regimes", response_model=DailyViewRegimeAccuracyResponse)
@cached("signals:daily-accuracy:regimes", ttl=300)
async def get_daily_view_accuracy_regimes(
    window_days: int = Query(1, ge=1, le=30),
    sector: str | None = Query(None),
    direction: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    min_conviction: float = Query(DEFAULT_MIN_CONVICTION, ge=0.0, le=1.0),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await _fetch_regime_rows(
        db,
        window_days=window_days,
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
    )
    return DailyViewRegimeAccuracyResponse(regimes=aggregate_by_label(rows, "regime"))


async def _fetch_regime_rows(
    db: AsyncSession,
    *,
    window_days: int,
    sector: str | None,
    direction: str | None,
    date_from: date | None,
    date_to: date | None,
    min_conviction: float,
) -> list[AccuracyRow]:
    regime_sq = (
        select(
            Signal.stock_id,
            Signal.trading_date,
            func.mode().within_group(Signal.market_regime).label("regime"),
        )
        .where(Signal.composite_score.isnot(None))
        .where(Signal.market_regime.isnot(None))
        .group_by(Signal.stock_id, Signal.trading_date)
        .subquery()
    )
    onclause, _inner = _outcome_join(window_days, True)
    stmt = (
        select(
            DailySignalView.conviction,
            DailySignalViewOutcome.is_correct,
            DailySignalViewOutcome.excess_return_pct,
            DailySignalViewOutcome.price_change_pct,
            DailySignalView.trading_date,
            Sector.name,
            regime_sq.c.regime,
        )
        .select_from(DailySignalView)
        .join(DailySignalViewOutcome, onclause)
        .join(Stock, DailySignalView.stock_id == Stock.id)
        .join(Sector, Stock.sector_id == Sector.id)
        .join(
            regime_sq,
            (regime_sq.c.stock_id == DailySignalView.stock_id)
            & (regime_sq.c.trading_date == DailySignalView.trading_date),
        )
    )
    stmt = _apply_view_filters(
        stmt,
        sector=sector,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        min_conviction=min_conviction,
    )
    result = await db.execute(stmt)
    rows: list[AccuracyRow] = []
    for row in result.all():
        excess = row.excess_return_pct if row.excess_return_pct is not None else row.price_change_pct
        rows.append(
            AccuracyRow(
                conviction=float(row.conviction),
                is_correct=bool(row.is_correct),
                excess_return=None if excess is None else float(excess),
                trading_date=row.trading_date,
                sector=row.name,
                regime=row.regime,
            )
        )
    return rows
