"""ML model training Celery task.

Trains per-sector LightGBM classifiers from evaluated signal outcomes.
Follows the weight_optimizer.py pattern: gate on settings, per-sector + global,
upsert results to ml_models table. Runs daily at 4:30 AM after weight optimizer.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.ml_model import MLModel
from app.models.sector import Sector
from app.models.signal import Signal
from app.models.signal_outcome import SignalOutcome
from app.models.stock import Stock
from worker.celery_app import celery_app
from worker.utils.async_task import run_async
from worker.utils.ml_trainer import FEATURE_NAMES, train_model

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.signals.ml_trainer_task.train_ml_models",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def train_ml_models(self):
    """Train per-sector LightGBM models from outcome data. Called at 4:30 AM by beat."""
    if not settings.ml_ensemble_enabled:
        return {"skipped": True, "reason": "ml_ensemble_disabled"}
    try:
        return run_async(_train_ml_models_async())
    except Exception as exc:
        logger.error(f"ML model training failed: {exc}")
        raise self.retry(exc=exc)


async def _train_ml_models_async() -> dict:
    """Train per-sector + global ML models from evaluated outcomes."""
    now = datetime.now(timezone.utc)
    lookback_cutoff = now - timedelta(days=settings.feedback_lookback_days)
    sectors_trained = 0
    global_trained = False

    async with async_session() as session:
        # Get all active sectors
        result = await session.execute(select(Sector).where(Sector.is_active == True))  # noqa: E712
        sectors = result.scalars().all()

        # Collect all training data for global model
        all_features: list[list[float]] = []
        all_labels: list[bool] = []

        for sector in sectors:
            # Check if retrain is needed
            existing = await _get_existing_model(session, sector.id)
            if existing and existing.trained_at:
                days_since = (now - existing.trained_at).days
                if days_since < settings.ml_retrain_interval_days:
                    logger.info(f"Skipping {sector.name}: retrained {days_since}d ago")
                    continue

            features, labels = await _get_training_data(session, sector.id, lookback_cutoff)

            if len(features) < settings.ml_min_training_samples:
                logger.info(f"Skipping {sector.name}: {len(features)} < {settings.ml_min_training_samples} samples")
                continue

            # Determine version
            version = (existing.model_version + 1) if existing else 1

            training_result = train_model(
                features=features,
                labels=labels,
                model_dir=settings.ml_model_dir,
                sector_name=sector.name,
                version=version,
                validation_split=settings.ml_validation_split,
            )

            if training_result:
                await _upsert_ml_model(session, sector.id, version, training_result)
                sectors_trained += 1
                logger.info(
                    f"Trained ML model for {sector.name}: "
                    f"accuracy={training_result.validation_accuracy:.1f}%, "
                    f"f1={training_result.validation_f1:.4f}, "
                    f"samples={training_result.training_samples}"
                )

            # Accumulate for global model
            all_features.extend(features)
            all_labels.extend(labels)

        # Train global fallback model (sector_id = NULL)
        if len(all_features) >= settings.ml_min_training_samples:
            existing_global = await _get_existing_model(session, None)
            global_version = (existing_global.model_version + 1) if existing_global else 1

            global_result = train_model(
                features=all_features,
                labels=all_labels,
                model_dir=settings.ml_model_dir,
                sector_name="global",
                version=global_version,
                validation_split=settings.ml_validation_split,
            )

            if global_result:
                await _upsert_ml_model(session, None, global_version, global_result)
                global_trained = True
                logger.info(
                    f"Trained global ML model: "
                    f"accuracy={global_result.validation_accuracy:.1f}%, "
                    f"samples={global_result.training_samples}"
                )

        await session.commit()

    logger.info(f"ML training complete: {sectors_trained} sectors, global={global_trained}")
    return {"sectors_trained": sectors_trained, "global_trained": global_trained}


async def _get_training_data(
    session: AsyncSession,
    sector_id: int | None,
    cutoff: datetime,
) -> tuple[list[list[float]], list[bool]]:
    """Fetch feature matrix and labels from evaluated signals."""
    query = (
        select(
            Signal.sentiment_score,
            Signal.sentiment_volume_score,
            Signal.price_score,
            Signal.volume_score,
            Signal.rsi_score,
            Signal.trend_score,
            SignalOutcome.is_correct,
        )
        .join(Signal, SignalOutcome.signal_id == Signal.id)
        .join(Stock, Signal.stock_id == Stock.id)
        .where(SignalOutcome.window_days == 5)
        .where(SignalOutcome.evaluated_at >= cutoff)
        .where(Signal.direction.in_(["bullish", "bearish"]))
        .order_by(Signal.generated_at.asc())  # chronological for time-series split
    )

    if sector_id is not None:
        query = query.where(Stock.sector_id == sector_id)

    result = await session.execute(query)
    rows = result.all()

    features: list[list[float]] = []
    labels: list[bool] = []

    for row in rows:
        feature_vec = [
            float(row.sentiment_score) if row.sentiment_score is not None else 0.0,
            float(row.sentiment_volume_score) if row.sentiment_volume_score is not None else 0.0,
            float(row.price_score) if row.price_score is not None else 0.0,
            float(row.volume_score) if row.volume_score is not None else 0.0,
            float(row.rsi_score) if row.rsi_score is not None else 0.0,
            float(row.trend_score) if row.trend_score is not None else 0.0,
        ]
        features.append(feature_vec)
        labels.append(row.is_correct)

    return features, labels


async def _get_existing_model(session: AsyncSession, sector_id: int | None) -> MLModel | None:
    """Get the existing active model for a sector (or global if sector_id is None)."""
    if sector_id is not None:
        query = select(MLModel).where(MLModel.sector_id == sector_id)
    else:
        query = select(MLModel).where(MLModel.sector_id.is_(None))
    result = await session.execute(query)
    return result.scalars().first()


async def _upsert_ml_model(
    session: AsyncSession,
    sector_id: int | None,
    version: int,
    training_result,
) -> None:
    """Insert or update ML model metadata for a sector."""
    stmt = pg_insert(MLModel).values(
        sector_id=sector_id,
        model_version=version,
        feature_count=len(FEATURE_NAMES),
        training_samples=training_result.training_samples,
        validation_accuracy=training_result.validation_accuracy,
        validation_f1=training_result.validation_f1,
        model_path=training_result.model_path,
        is_active=True,
        trained_at=datetime.now(timezone.utc),
        feature_importances=json.dumps(training_result.feature_importances),
        training_config=json.dumps(training_result.training_config),
    )
    stmt = stmt.on_conflict_on_constraint("ml_models_sector_id_key").do_update(
        set_={
            "model_version": stmt.excluded.model_version,
            "training_samples": stmt.excluded.training_samples,
            "validation_accuracy": stmt.excluded.validation_accuracy,
            "validation_f1": stmt.excluded.validation_f1,
            "model_path": stmt.excluded.model_path,
            "is_active": stmt.excluded.is_active,
            "trained_at": stmt.excluded.trained_at,
            "feature_importances": stmt.excluded.feature_importances,
            "training_config": stmt.excluded.training_config,
        }
    )
    await session.execute(stmt)
