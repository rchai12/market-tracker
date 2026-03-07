"""Adaptive weight computation Celery task.

Analyzes historical signal accuracy per sector to compute optimal weights
for the 4 signal components. Runs daily at 4 AM after maintenance.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.sector import Sector
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.models.signal_weight import SignalWeight
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.signals.weight_optimizer.compute_adaptive_weights",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def compute_adaptive_weights(self):
    """Compute per-sector adaptive weights from evaluated outcomes. Called at 4 AM by beat."""
    if not settings.feedback_enabled:
        return {"skipped": True, "reason": "feedback_disabled"}
    try:
        return run_async(_compute_adaptive_weights_async())
    except Exception as exc:
        logger.error(f"Adaptive weight computation failed: {exc}")
        raise self.retry(exc=exc)


async def _compute_adaptive_weights_async() -> dict:
    """Compute per-sector adaptive weights based on component-level accuracy."""
    now = datetime.now(timezone.utc)
    lookback_cutoff = now - timedelta(days=settings.feedback_lookback_days)
    sectors_updated = 0

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

        # Global fallback (sector_id = NULL)
        global_weights = await _compute_sector_weights(session, None, lookback_cutoff)
        if global_weights:
            await _upsert_weights(session, None, global_weights)
            logger.info(
                f"Updated global weights: accuracy={global_weights['accuracy_pct']:.1f}%, "
                f"n={global_weights['sample_count']}"
            )

        await session.commit()

    logger.info(f"Adaptive weight computation complete: {sectors_updated} sectors updated")
    return {"sectors_updated": sectors_updated}


async def _compute_sector_weights(
    session: AsyncSession,
    sector_id: int | None,
    cutoff: datetime,
) -> dict | None:
    """Compute adaptive weights for a sector based on component accuracy.

    For each evaluated signal, check if each component's sign aligned with
    the actual price direction. Higher component accuracy → higher weight.
    """
    query = (
        select(
            Signal.sentiment_score,
            Signal.price_score,
            Signal.volume_score,
            Signal.direction,
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

    result = await session.execute(query)
    rows = result.all()

    if len(rows) < settings.feedback_min_samples:
        return None

    component_correct = {"sentiment_momentum": 0, "sentiment_volume": 0, "price_momentum": 0, "volume_anomaly": 0}
    component_total = {k: 0 for k in component_correct}
    total_correct = 0

    for row in rows:
        actual_dir = 1.0 if float(row.price_change_pct) > 0 else -1.0

        # Sentiment momentum (stored as sentiment_score)
        if row.sentiment_score is not None:
            if (1.0 if float(row.sentiment_score) > 0 else -1.0) == actual_dir:
                component_correct["sentiment_momentum"] += 1
            component_total["sentiment_momentum"] += 1

        # Price momentum (stored as price_score)
        if row.price_score is not None:
            if (1.0 if float(row.price_score) > 0 else -1.0) == actual_dir:
                component_correct["price_momentum"] += 1
            component_total["price_momentum"] += 1

        # Volume anomaly (stored as volume_score)
        if row.volume_score is not None:
            if (1.0 if float(row.volume_score) > 0 else -1.0) == actual_dir:
                component_correct["volume_anomaly"] += 1
            component_total["volume_anomaly"] += 1

        # Sentiment volume not stored separately — use overall correctness as proxy
        component_correct["sentiment_volume"] += 1 if row.is_correct else 0
        component_total["sentiment_volume"] += 1

        if row.is_correct:
            total_correct += 1

    # Compute accuracy ratios
    accuracies = {}
    for key in component_correct:
        if component_total[key] > 0:
            accuracies[key] = component_correct[key] / component_total[key]
        else:
            accuracies[key] = 0.5  # neutral prior

    # Normalize to weights summing to 1.0
    raw_weights = {k: max(v, 0.01) for k, v in accuracies.items()}
    total_raw = sum(raw_weights.values())
    normalized = {k: v / total_raw for k, v in raw_weights.items()}

    clamped = clamp_weights(normalized, settings.feedback_weight_min, settings.feedback_weight_max)

    overall_accuracy = (total_correct / len(rows) * 100) if rows else 0

    return {
        "sentiment_momentum": round(clamped["sentiment_momentum"], 4),
        "sentiment_volume": round(clamped["sentiment_volume"], 4),
        "price_momentum": round(clamped["price_momentum"], 4),
        "volume_anomaly": round(clamped["volume_anomaly"], 4),
        "sample_count": len(rows),
        "accuracy_pct": round(overall_accuracy, 2),
    }


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
            # All keys hit bounds — distribute deficit/surplus evenly while respecting bounds
            total = sum(clamped.values())
            if abs(total - 1.0) < 1e-9:
                return clamped
            # Redistribute: give each key an equal share of the gap
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


async def _upsert_weights(session: AsyncSession, sector_id: int | None, weights: dict) -> None:
    """Insert or update weights for a sector."""
    stmt = pg_insert(SignalWeight).values(
        sector_id=sector_id,
        sentiment_momentum=weights["sentiment_momentum"],
        sentiment_volume=weights["sentiment_volume"],
        price_momentum=weights["price_momentum"],
        volume_anomaly=weights["volume_anomaly"],
        sample_count=weights["sample_count"],
        accuracy_pct=weights["accuracy_pct"],
        computed_at=datetime.now(timezone.utc),
    )
    stmt = stmt.on_conflict_on_constraint("signal_weights_sector_id_key").do_update(
        set_={
            "sentiment_momentum": stmt.excluded.sentiment_momentum,
            "sentiment_volume": stmt.excluded.sentiment_volume,
            "price_momentum": stmt.excluded.price_momentum,
            "volume_anomaly": stmt.excluded.volume_anomaly,
            "sample_count": stmt.excluded.sample_count,
            "accuracy_pct": stmt.excluded.accuracy_pct,
            "computed_at": stmt.excluded.computed_at,
        }
    )
    await session.execute(stmt)
