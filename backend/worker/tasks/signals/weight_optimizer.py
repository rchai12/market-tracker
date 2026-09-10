"""Adaptive weight computation Celery task.

Analyzes historical signal accuracy per sector (and per market regime) to
compute optimal weights for the predictive components. Votes are weighted by
``abs(price_change_pct)`` so large moves count more than noise. Analyst is
tracked alongside earnings/options. RSI and trend are regime-only and always
stored as 0.0. Runs daily at 4 AM after maintenance.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.regime_adaptive_weight import RegimeAdaptiveWeight
from app.models.sector import Sector
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)

REGIMES = ("overbought", "oversold", "trending_up", "trending_down", "sideways")


@celery_app.task(
    name="worker.tasks.signals.weight_optimizer.compute_adaptive_weights",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def compute_adaptive_weights(self):
    """Compute per-sector and per-regime adaptive weights. Called at 4 AM by beat."""
    if not settings.feedback_enabled:
        return {"skipped": True, "reason": "feedback_disabled"}
    try:
        return run_async(_compute_adaptive_weights_async())
    except Exception as exc:
        logger.error(f"Adaptive weight computation failed: {exc}")
        raise self.retry(exc=exc)


async def _compute_adaptive_weights_async() -> dict:
    """Compute per-sector and per-regime adaptive weights from outcomes."""
    now = datetime.now(UTC)
    lookback_cutoff = now - timedelta(days=settings.feedback_lookback_days)
    sectors_updated = 0
    regimes_updated = 0

    async with async_session() as session:
        result = await session.execute(select(Sector).where(Sector.is_active == True))  # noqa: E712
        sectors = result.scalars().all()

        for sector in sectors:
            weights = await _compute_sector_weights(session, sector.id, lookback_cutoff)
            if weights:
                await _upsert_weights(session, sector.id, weights)
                sectors_updated += 1
                logger.info(
                    f"Updated weights for {sector.name}: "
                    f"sm={weights['sentiment_momentum']:.4f} sv={weights['sentiment_volume']:.4f} "
                    f"pm={weights['price_momentum']:.4f} va={weights['volume_anomaly']:.4f} "
                    f"(accuracy={weights['accuracy_pct']:.1f}%, n={weights['sample_count']})"
                )

        global_weights = await _compute_sector_weights(session, None, lookback_cutoff)
        if global_weights:
            await _upsert_weights(session, None, global_weights)
            logger.info(
                f"Updated global weights: accuracy={global_weights['accuracy_pct']:.1f}%, "
                f"n={global_weights['sample_count']}"
            )

        sector_ids = [sector.id for sector in sectors] + [None]
        regimes_updated = await _compute_regime_weights(session, sector_ids, lookback_cutoff)

        await session.commit()

    logger.info(
        "Adaptive weight computation complete: %s sectors, %s regime pairs updated",
        sectors_updated,
        regimes_updated,
    )
    return {"sectors_updated": sectors_updated, "regimes_updated": regimes_updated}


async def _compute_regime_weights(
    session: AsyncSession,
    sector_ids: list[int | None],
    cutoff: datetime,
) -> int:
    """Learn weights per (sector_id, regime) when that pair has enough samples."""
    updated = 0
    for sector_id in sector_ids:
        for regime in REGIMES:
            weights = await _compute_sector_weights(session, sector_id, cutoff, regime=regime)
            if not weights:
                continue
            await _upsert_regime_weights(session, sector_id, regime, weights)
            updated += 1
            logger.info(
                "Updated regime weights sector=%s regime=%s n=%s accuracy=%.1f%%",
                sector_id,
                regime,
                weights["sample_count"],
                weights["accuracy_pct"],
            )
    return updated


async def _compute_sector_weights(
    session: AsyncSession,
    sector_id: int | None,
    cutoff: datetime,
    regime: str | None = None,
) -> dict | None:
    """Compute adaptive weights from 5-day outcomes, optionally filtered by regime."""
    query = (
        select(
            Signal.sentiment_score,
            Signal.price_score,
            Signal.volume_score,
            Signal.options_score,
            Signal.earnings_score,
            Signal.analyst_score,
            Signal.direction,
            Signal.market_regime,
            SignalOutcome.is_correct,
            SignalOutcome.price_change_pct,
        )
        .join(Signal, SignalOutcome.signal_id == Signal.id)
        .join(Stock, Signal.stock_id == Stock.id)
        .where(SignalOutcome.window_days == 5)
        .where(SignalOutcome.evaluated_at >= cutoff)
        .where(Signal.direction.in_(["bullish", "bearish"]))
    )

    if sector_id is not None:
        query = query.where(Stock.sector_id == sector_id)
    if regime is not None:
        query = query.where(Signal.market_regime == regime)

    result = await session.execute(query)
    return _weights_from_rows(result.all())


def _weights_from_rows(rows: list) -> dict | None:
    """Return-weighted component accuracies → clamped, normalized weights.

    Each signal votes with ``abs(price_change_pct)`` so a correct 5% move
    outweighs a correct 0.1% move. Returns None below ``feedback_min_samples``.
    """
    if len(rows) < settings.feedback_min_samples:
        return None

    components = ["sentiment_momentum", "sentiment_volume", "price_momentum", "volume_anomaly", "earnings", "analyst"]
    if settings.options_flow_enabled:
        components.append("options")
    component_correct = {k: 0.0 for k in components}
    component_total = {k: 0.0 for k in components}
    total_correct = 0

    for row in rows:
        pct = float(row.price_change_pct) if row.price_change_pct is not None else 0.0
        magnitude = abs(pct)
        actual_dir = 1.0 if pct > 0 else -1.0

        _credit(component_correct, component_total, "sentiment_momentum", row.sentiment_score, actual_dir, magnitude)
        _credit(component_correct, component_total, "price_momentum", row.price_score, actual_dir, magnitude)
        _credit(component_correct, component_total, "volume_anomaly", row.volume_score, actual_dir, magnitude)
        _credit(
            component_correct,
            component_total,
            "earnings",
            row.earnings_score,
            actual_dir,
            magnitude,
            min_abs=0.01,
        )
        _credit(
            component_correct,
            component_total,
            "analyst",
            row.analyst_score,
            actual_dir,
            magnitude,
            min_abs=0.01,
        )
        if settings.options_flow_enabled:
            _credit(component_correct, component_total, "options", row.options_score, actual_dir, magnitude)

        component_correct["sentiment_volume"] += magnitude if row.is_correct else 0.0
        component_total["sentiment_volume"] += magnitude

        if row.is_correct:
            total_correct += 1

    accuracies = {}
    for key in component_correct:
        if component_total[key] > 0:
            accuracies[key] = component_correct[key] / component_total[key]
        else:
            accuracies[key] = 0.5

    raw_weights = {k: max(v, 0.01) for k, v in accuracies.items()}
    total_raw = sum(raw_weights.values())
    normalized = {k: v / total_raw for k, v in raw_weights.items()}

    clamped = clamp_weights(normalized, settings.feedback_weight_min, settings.feedback_weight_max)

    overall_accuracy = (total_correct / len(rows) * 100) if rows else 0

    result_weights = {
        "sentiment_momentum": round(clamped["sentiment_momentum"], 4),
        "sentiment_volume": round(clamped["sentiment_volume"], 4),
        "price_momentum": round(clamped["price_momentum"], 4),
        "volume_anomaly": round(clamped["volume_anomaly"], 4),
        "earnings": round(clamped.get("earnings", 0.10), 4),
        "analyst": round(clamped.get("analyst", 0.07), 4),
        "sample_count": len(rows),
        "accuracy_pct": round(overall_accuracy, 2),
    }
    if settings.options_flow_enabled:
        result_weights["options"] = round(clamped.get("options", 0.08), 4)
    return result_weights


def _credit(
    component_correct: dict[str, float],
    component_total: dict[str, float],
    key: str,
    score: float | None,
    actual_dir: float,
    magnitude: float,
    min_abs: float = 0.0,
) -> None:
    if score is None:
        return
    val = float(score)
    if min_abs and abs(val) <= min_abs:
        return
    sign_matches = (1.0 if val > 0 else -1.0) == actual_dir
    component_correct[key] += magnitude if sign_matches else 0.0
    component_total[key] += magnitude


def clamp_weights(weights: dict[str, float], min_w: float, max_w: float) -> dict[str, float]:
    """Clamp weights to [min_w, max_w] and re-normalize to sum to 1.0.

    Iteratively clamps extremes and redistributes remaining budget.
    """
    result = dict(weights)

    for _ in range(10):
        clamped = {}
        free_keys = []
        budget = 1.0

        for k, v in result.items():
            if v < min_w:
                clamped[k] = min_w
                budget -= min_w
            elif v > max_w:
                clamped[k] = max_w
                budget -= max_w
            else:
                free_keys.append(k)

        if not free_keys:
            total = sum(clamped.values())
            if abs(total - 1.0) < 1e-9:
                return clamped
            gap = 1.0 - total
            per_key = gap / len(clamped)
            for k in clamped:
                clamped[k] = max(min_w, min(max_w, clamped[k] + per_key))
            result = clamped
            continue

        free_total = sum(result[k] for k in free_keys)
        if free_total <= 0:
            share = budget / len(free_keys)
            for k in free_keys:
                clamped[k] = share
        else:
            for k in free_keys:
                clamped[k] = (result[k] / free_total) * budget

        result = clamped

        if all(min_w <= v <= max_w for v in result.values()):
            break

    return result


def _weight_values(weights: dict) -> dict:
    return {
        "sentiment_momentum": weights["sentiment_momentum"],
        "sentiment_volume": weights["sentiment_volume"],
        "price_momentum": weights["price_momentum"],
        "volume_anomaly": weights["volume_anomaly"],
        "rsi": 0.0,
        "trend": 0.0,
        "options": weights.get("options", 0.08),
        "earnings": weights.get("earnings", 0.10),
        "analyst": weights.get("analyst", 0.07),
        "sample_count": weights["sample_count"],
        "accuracy_pct": weights["accuracy_pct"],
        "computed_at": datetime.now(UTC),
    }


async def _upsert_weights(session: AsyncSession, sector_id: int | None, weights: dict) -> None:
    """Insert or update sector-level weights."""
    values = {"sector_id": sector_id, **_weight_values(weights)}
    stmt = pg_insert(SignalWeight).values(**values)
    update_set = {k: getattr(stmt.excluded, k) for k in values if k != "sector_id"}
    stmt = stmt.on_conflict_on_constraint("signal_weights_sector_id_key").do_update(set_=update_set)
    await session.execute(stmt)


async def _upsert_regime_weights(
    session: AsyncSession,
    sector_id: int | None,
    regime: str,
    weights: dict,
) -> None:
    """Insert or update (sector, regime) weights."""
    values = {"sector_id": sector_id, "regime": regime, **_weight_values(weights)}
    stmt = pg_insert(RegimeAdaptiveWeight).values(**values)
    update_set = {k: getattr(stmt.excluded, k) for k in values if k not in ("sector_id", "regime")}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_regime_adaptive_weights_sector_regime",
        set_=update_set,
    )
    await session.execute(stmt)
