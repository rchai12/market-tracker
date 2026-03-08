"""LightGBM ML signal ensemble — pure training and inference module.

No database or Celery dependencies. Receives data as plain lists/dicts
and returns results as dataclasses. Analogous to technical_indicators.py.
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "sentiment_momentum",
    "sentiment_volume",
    "price_momentum",
    "volume_anomaly",
    "rsi_score",
    "trend_score",
]

# Conservative params for ARM free tier + small datasets
DEFAULT_PARAMS = {
    "objective": "binary",
    "metric": ["binary_logloss", "auc"],
    "num_leaves": 15,
    "learning_rate": 0.05,
    "min_data_in_leaf": 10,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "num_threads": 1,
}
DEFAULT_NUM_BOOST_ROUND = 200
DEFAULT_EARLY_STOPPING_ROUNDS = 20

# Module-level model cache: model_path -> Booster
_model_cache: dict[str, lgb.Booster] = {}


@dataclass
class TrainingResult:
    model_path: str
    training_samples: int
    validation_accuracy: float
    validation_f1: float
    feature_importances: dict[str, float]
    training_config: dict


@dataclass
class PredictionResult:
    ml_score: float       # signed probability: positive = bullish, negative = bearish
    ml_direction: str     # "bullish" / "bearish" / "neutral"
    ml_confidence: float  # raw probability [0, 1]


def _accuracy(y_true: list, y_pred: list) -> float:
    """Compute accuracy from two lists of 0/1 values."""
    if not y_true:
        return 0.0
    return sum(1 for a, b in zip(y_true, y_pred) if a == b) / len(y_true)


def _f1(y_true: list, y_pred: list) -> float:
    """Compute F1 score from two lists of 0/1 values."""
    tp = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y_true, y_pred) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 0)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def train_model(
    features: list[list[float]],
    labels: list[bool],
    model_dir: str,
    sector_name: str,
    version: int,
    validation_split: float = 0.2,
) -> TrainingResult | None:
    """Train a LightGBM binary classifier.

    Args:
        features: N x 6 matrix of component scores.
        labels: is_correct from SignalOutcome.
        model_dir: Base directory for model files.
        sector_name: Sector slug for file path.
        version: Model version number.
        validation_split: Fraction of data for validation.

    Returns:
        TrainingResult on success, None if insufficient data after split.
    """
    n = len(features)
    if n < 20:
        return None

    X = np.array(features, dtype=np.float64)
    y = np.array([1 if label else 0 for label in labels], dtype=np.int32)

    # Chronological train/val split (not random — time-series data)
    split_idx = int(n * (1 - validation_split))
    if split_idx < 10 or (n - split_idx) < 5:
        return None

    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_NAMES, free_raw_data=False)
    val_data = lgb.Dataset(X_val, label=y_val, feature_name=FEATURE_NAMES, reference=train_data, free_raw_data=False)

    callbacks = [lgb.early_stopping(DEFAULT_EARLY_STOPPING_ROUNDS, verbose=False)]

    model = lgb.train(
        DEFAULT_PARAMS,
        train_data,
        num_boost_round=DEFAULT_NUM_BOOST_ROUND,
        valid_sets=[val_data],
        callbacks=callbacks,
    )

    # Evaluate on validation set
    val_probs = model.predict(X_val)
    val_preds = [1 if p > 0.5 else 0 for p in val_probs]
    val_accuracy = _accuracy(y_val.tolist(), val_preds)
    val_f1 = _f1(y_val.tolist(), val_preds)

    # Feature importances (gain-based)
    raw_importances = model.feature_importance(importance_type="gain")
    total_imp = sum(raw_importances) if sum(raw_importances) > 0 else 1.0
    importances = {name: round(float(imp / total_imp), 4) for name, imp in zip(FEATURE_NAMES, raw_importances)}

    # Save model
    sector_slug = sector_name.lower().replace(" ", "_").replace("/", "_")
    model_path = Path(model_dir) / sector_slug / f"model_v{version}.txt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))

    # Update cache
    _model_cache[str(model_path)] = model

    logger.info(
        f"Trained ML model for {sector_name}: accuracy={val_accuracy:.3f}, f1={val_f1:.3f}, "
        f"samples={n}, path={model_path}"
    )

    return TrainingResult(
        model_path=str(model_path),
        training_samples=n,
        validation_accuracy=round(val_accuracy * 100, 2),
        validation_f1=round(val_f1, 4),
        feature_importances=importances,
        training_config={**DEFAULT_PARAMS, "num_boost_round": DEFAULT_NUM_BOOST_ROUND},
    )


def load_model(model_path: str) -> lgb.Booster | None:
    """Load a LightGBM model from disk, with caching."""
    if model_path in _model_cache:
        return _model_cache[model_path]

    path = Path(model_path)
    if not path.exists():
        logger.warning(f"ML model file not found: {model_path}")
        return None

    model = lgb.Booster(model_file=str(path))
    _model_cache[model_path] = model
    return model


def predict(
    model_path: str,
    features: list[float],
    composite_direction: str,
    confidence_threshold: float = 0.55,
) -> PredictionResult | None:
    """Run inference on a single feature vector.

    The model predicts P(is_correct). We interpret this relative to the
    rule-based direction:
    - High P(correct) → agree with rule-based direction
    - Low P(correct) → disagree → opposite direction
    - Near 0.5 → neutral

    Args:
        model_path: Path to saved model file.
        features: 6 component scores.
        composite_direction: Rule-based direction ("bullish"/"bearish"/"neutral").
        confidence_threshold: Minimum probability to assign a direction.

    Returns:
        PredictionResult or None if model can't be loaded.
    """
    model = load_model(model_path)
    if model is None:
        return None

    X = np.array([features], dtype=np.float64)
    prob_correct = float(model.predict(X)[0])

    # Convert probability to signed score and direction
    if prob_correct >= confidence_threshold:
        # Model agrees the rule-based signal is likely correct
        ml_direction = composite_direction if composite_direction != "neutral" else "neutral"
        sign = 1.0 if composite_direction == "bullish" else -1.0 if composite_direction == "bearish" else 0.0
        ml_score = sign * prob_correct
    elif prob_correct <= (1 - confidence_threshold):
        # Model disagrees — opposite direction
        if composite_direction == "bullish":
            ml_direction = "bearish"
            ml_score = -(1 - prob_correct)
        elif composite_direction == "bearish":
            ml_direction = "bullish"
            ml_score = (1 - prob_correct)
        else:
            ml_direction = "neutral"
            ml_score = 0.0
    else:
        # Uncertain — neutral
        ml_direction = "neutral"
        ml_score = 0.0

    return PredictionResult(
        ml_score=round(ml_score, 5),
        ml_direction=ml_direction,
        ml_confidence=round(prob_correct, 4),
    )


def clear_cache() -> None:
    """Clear the model cache. Useful for testing."""
    _model_cache.clear()
