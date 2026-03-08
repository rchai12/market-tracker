"""Backtesting engine package.

Re-exports all public API for backward compatibility with
``from worker.utils.backtester import ...`` style imports.
"""

from .benchmark import compute_benchmark
from .engine import aggregate_backtest_results, run_backtest
from .metrics import compute_metrics
from .models import (
    DEFAULT_WEIGHTS,
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
    TECHNICAL_WEIGHTS,
    WARMUP_DAYS,
    BacktestConfig,
    BacktestResult,
    BenchmarkResult,
    EquityPoint,
    OHLCVRow,
    SentimentRow,
    TradeRecord,
)
from .signals import (
    classify_direction,
    classify_strength,
    compute_price_momentum_from_closes,
    compute_rsi_score_from_closes,
    compute_sentiment_momentum_from_data,
    compute_sentiment_volume_from_data,
    compute_trend_score_from_closes,
    compute_volume_anomaly_from_data,
)

__all__ = [
    # Models / data classes
    "BacktestConfig",
    "BacktestResult",
    "BenchmarkResult",
    "EquityPoint",
    "OHLCVRow",
    "SentimentRow",
    "TradeRecord",
    # Constants
    "DEFAULT_WEIGHTS",
    "MODERATE_THRESHOLD",
    "STRONG_THRESHOLD",
    "TECHNICAL_WEIGHTS",
    "WARMUP_DAYS",
    # Engine
    "aggregate_backtest_results",
    "run_backtest",
    # Signals
    "classify_direction",
    "classify_strength",
    "compute_price_momentum_from_closes",
    "compute_rsi_score_from_closes",
    "compute_sentiment_momentum_from_data",
    "compute_sentiment_volume_from_data",
    "compute_trend_score_from_closes",
    "compute_volume_anomaly_from_data",
    # Metrics
    "compute_metrics",
    # Benchmark
    "compute_benchmark",
]
