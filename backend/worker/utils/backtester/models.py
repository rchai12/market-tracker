"""Data classes and constants for the backtesting engine."""

from dataclasses import dataclass
from datetime import date

from worker.utils.signal_formula import MODERATE_THRESHOLD, STRONG_THRESHOLD, default_weights

# Live formula defaults (40/25/20/15). Technical mode uses the same weights
# with sentiment inputs omitted (treated as 0.0) — "live scoring without news".
_LIVE_DEFAULTS = default_weights(has_options=False, has_earnings=False)
DEFAULT_WEIGHTS = {k: v for k, v in _LIVE_DEFAULTS.items() if k != "source"}
TECHNICAL_WEIGHTS = DEFAULT_WEIGHTS

# ── Parameters ──
WARMUP_DAYS = 60  # Need 50 for SMA50 + buffer
SENTIMENT_HALF_LIFE_HOURS = 6
BASELINE_DAYS = 20
PRICE_MOMENTUM_DAYS = 5
RSI_PERIOD = 14
RSI_LOOKBACK = 30
TREND_LOOKBACK = 60


# ── Data classes ──


@dataclass
class OHLCVRow:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class SentimentRow:
    """Pre-aggregated daily sentiment for a stock."""

    date: date
    avg_positive: float
    avg_negative: float
    article_count: int


@dataclass
class BacktestConfig:
    mode: str = "technical"  # "technical" or "full"
    starting_capital: float = 10000.0
    min_signal_strength: str = "moderate"  # "moderate" or "strong"
    weights: dict | None = None  # Override weights, or None for defaults
    commission_pct: float = 0.0  # 0 for backward compat; API defaults to 0.001
    slippage_pct: float = 0.0  # 0 for backward compat; API defaults to 0.0005
    position_size_pct: float = 100.0  # 100% = all-in (current behavior)
    stop_loss_pct: float | None = None  # e.g. 5.0 = exit if price drops 5%
    take_profit_pct: float | None = None  # e.g. 20.0 = exit if price rises 20%


@dataclass
class TradeRecord:
    ticker: str
    action: str  # "buy" or "sell"
    trade_date: date
    price: float
    shares: float
    position_value: float
    portfolio_equity: float
    signal_score: float
    signal_direction: str
    signal_strength: str
    return_pct: float | None = None  # Set on sell trades
    exit_reason: str | None = None  # "signal", "stop_loss", "take_profit", "end_of_period"


@dataclass
class EquityPoint:
    date: date
    equity: float


@dataclass
class BacktestResult:
    equity_curve: list[EquityPoint]
    trades: list[TradeRecord]
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float | None
    max_drawdown_pct: float
    win_rate_pct: float | None
    total_trades: int
    avg_win_pct: float | None
    avg_loss_pct: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    final_equity: float


@dataclass
class BenchmarkResult:
    total_return_pct: float
    annualized_return_pct: float
    alpha: float
    beta: float | None
    equity_curve: list[EquityPoint]
