"""Pure backtesting engine — no database dependencies.

Takes pre-fetched OHLCV data (and optionally sentiment data), replays signal
generation day by day, simulates trades, and returns an equity curve with
performance metrics.

Two modes:
- "technical": Uses only OHLCV-derived components (price momentum, volume anomaly,
  RSI, trend). Works for full 30+ year historical range.
- "full": Uses all 6 components including sentiment momentum and sentiment volume.
  Limited to the period since sentiment scraping began.
"""

import math
from dataclasses import dataclass, field
from datetime import date

from worker.utils.technical_indicators import compute_macd, compute_rsi, compute_sma

# ── Default weights (mirror signal_generator.py) ──
DEFAULT_WEIGHTS = {
    "sentiment_momentum": 0.30,
    "sentiment_volume": 0.20,
    "price_momentum": 0.15,
    "volume_anomaly": 0.10,
    "rsi": 0.15,
    "trend": 0.10,
}

# Technical-only weights (renormalized: price_momentum + volume_anomaly + rsi + trend)
TECHNICAL_WEIGHTS = {
    "price_momentum": 0.30,
    "volume_anomaly": 0.20,
    "rsi": 0.30,
    "trend": 0.20,
}

# ── Thresholds (mirror signal_generator.py) ──
STRONG_THRESHOLD = 0.6
MODERATE_THRESHOLD = 0.35

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


# ── Signal component functions (pure, no DB) ──


def compute_price_momentum_from_closes(closes: list[float]) -> float | None:
    """5-day price change, tanh-scaled to [-1, 1].

    Expects at least 6 closes (oldest first).
    """
    if len(closes) < 2:
        return None

    latest = closes[-1]
    # Use up to PRICE_MOMENTUM_DAYS back
    lookback = min(len(closes) - 1, PRICE_MOMENTUM_DAYS)
    oldest = closes[-(lookback + 1)]

    if oldest == 0:
        return None

    pct_change = (latest - oldest) / oldest
    return math.tanh(pct_change * 5)


def compute_volume_anomaly_from_data(
    closes: list[float], volumes: list[int]
) -> float | None:
    """Trading volume vs 20-day average, signed by price direction.

    Expects parallel closes and volumes arrays (oldest first), at least 3 entries.
    """
    if len(closes) < 3 or len(volumes) < 3:
        return None

    latest_volume = volumes[-1]
    latest_close = closes[-1]
    prev_close = closes[-2]

    if latest_volume is None or latest_volume == 0:
        return None

    # Average of previous volumes (excluding latest)
    prev_volumes = [v for v in volumes[:-1] if v and v > 0]
    if not prev_volumes:
        return None

    avg_volume = sum(prev_volumes) / len(prev_volumes)
    if avg_volume == 0:
        return None

    ratio = latest_volume / avg_volume
    magnitude = math.tanh(ratio - 1.0)

    if prev_close > 0:
        price_direction = 1.0 if latest_close >= prev_close else -1.0
    else:
        price_direction = 1.0

    return magnitude * price_direction


def compute_rsi_score_from_closes(closes: list[float]) -> float | None:
    """RSI(14) mapped to [-1, 1]: oversold = positive, overbought = negative.

    Expects at least 16 closes (oldest first).
    """
    if len(closes) < RSI_PERIOD + 2:
        return None

    rsi_values = compute_rsi(closes, period=RSI_PERIOD)
    latest_rsi = rsi_values[-1]
    if latest_rsi is None:
        return None

    centered = (50 - latest_rsi) / 50
    return math.tanh(centered * 2.5)


def compute_trend_score_from_closes(closes: list[float]) -> float | None:
    """Combined SMA crossover (60%) + MACD histogram (40%) trend score.

    Expects at least 52 closes (oldest first).
    """
    if len(closes) < 52:
        return None

    # SMA crossover component
    sma20 = compute_sma(closes, 20)
    sma50 = compute_sma(closes, 50)
    sma_score = 0.0
    if sma20[-1] is not None and sma50[-1] is not None and sma50[-1] != 0:
        sma_diff = (sma20[-1] - sma50[-1]) / sma50[-1]
        sma_score = math.tanh(sma_diff * 10)

    # MACD component
    macd_data = compute_macd(closes)
    macd_score = 0.0
    latest_macd = macd_data[-1]
    if latest_macd["histogram"] is not None and closes[-1] != 0:
        norm_hist = latest_macd["histogram"] / closes[-1]
        macd_score = math.tanh(norm_hist * 100)

    return 0.6 * sma_score + 0.4 * macd_score


def compute_sentiment_momentum_from_data(
    rows: list[SentimentRow], as_of_date: date
) -> float | None:
    """Exponentially weighted avg of daily sentiment, half-life 6h (~0.25 days).

    Looks back 2 days (48h equivalent in daily data).
    """
    if not rows:
        return None

    # Filter to rows within 2 days before as_of_date
    cutoff = _date_offset(as_of_date, -2)
    recent = [r for r in rows if cutoff <= r.date <= as_of_date and r.article_count > 0]

    if not recent:
        return None

    # Convert daily sentiment to half-life decay (use days, half-life = 0.25 days = 6h)
    half_life_days = SENTIMENT_HALF_LIFE_HOURS / 24.0
    decay_rate = math.log(2) / half_life_days
    weighted_sum = 0.0
    weight_total = 0.0

    for row in recent:
        sentiment_value = row.avg_positive - row.avg_negative
        days_ago = (as_of_date - row.date).days
        weight = math.exp(-decay_rate * days_ago) * row.article_count
        weighted_sum += sentiment_value * weight
        weight_total += weight

    if weight_total == 0:
        return None

    return weighted_sum / weight_total


def compute_sentiment_volume_from_data(
    rows: list[SentimentRow], as_of_date: date
) -> float | None:
    """Article count on as_of_date vs 20-day baseline, signed by net sentiment.

    Mirrors calc_sentiment_volume in signal_generator.
    """
    if not rows:
        return None

    # Today's articles
    today_rows = [r for r in rows if r.date == as_of_date]
    today_count = sum(r.article_count for r in today_rows)
    today_net = 0.0
    if today_rows:
        total_articles = sum(r.article_count for r in today_rows)
        if total_articles > 0:
            today_net = sum(
                (r.avg_positive - r.avg_negative) * r.article_count for r in today_rows
            ) / total_articles

    if today_count == 0:
        return None

    # Baseline: last 20 days excluding today
    cutoff = _date_offset(as_of_date, -BASELINE_DAYS)
    baseline_rows = [r for r in rows if cutoff <= r.date < as_of_date]
    baseline_total = sum(r.article_count for r in baseline_rows)
    baseline_days = max(len(set(r.date for r in baseline_rows)), 1)
    baseline_daily_avg = baseline_total / baseline_days

    if baseline_daily_avg == 0:
        ratio = min(today_count, 5.0)
    else:
        ratio = today_count / baseline_daily_avg

    magnitude = math.tanh(ratio - 1.0)
    direction_sign = 1.0 if today_net >= 0 else -1.0

    return magnitude * direction_sign


# ── Signal classification (mirrors signal_generator.py) ──


def classify_direction(composite: float) -> str:
    if composite > 0.01:
        return "bullish"
    elif composite < -0.01:
        return "bearish"
    return "neutral"


def classify_strength(composite: float) -> str:
    abs_score = abs(composite)
    if abs_score > STRONG_THRESHOLD:
        return "strong"
    elif abs_score > MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


# ── Core backtest engine ──


def run_backtest(
    ticker: str,
    ohlcv: list[OHLCVRow],
    config: BacktestConfig,
    sentiment_data: list[SentimentRow] | None = None,
) -> BacktestResult:
    """Run a backtest for a single ticker.

    Args:
        ticker: Stock ticker symbol.
        ohlcv: Chronologically ordered OHLCV data (oldest first).
        config: Backtest configuration.
        sentiment_data: Optional pre-aggregated daily sentiment data (for "full" mode).

    Returns:
        BacktestResult with equity curve, trades, and performance metrics.
    """
    if len(ohlcv) < WARMUP_DAYS + 1:
        return _empty_result(config.starting_capital)

    # Determine weights
    if config.weights:
        weights = config.weights
    elif config.mode == "technical":
        weights = TECHNICAL_WEIGHTS
    else:
        weights = DEFAULT_WEIGHTS

    # Determine minimum strength threshold
    min_strength_order = {"weak": 0, "moderate": 1, "strong": 2}
    min_strength_val = min_strength_order.get(config.min_signal_strength, 1)

    cash = config.starting_capital
    position: dict | None = None  # {"shares": float, "entry_price": float, "entry_date": date}
    equity_curve: list[EquityPoint] = []
    trades: list[TradeRecord] = []

    for i in range(WARMUP_DAYS, len(ohlcv)):
        today = ohlcv[i]
        history = ohlcv[: i + 1]

        # Compute signal components
        closes = [row.close for row in history]
        volumes = [row.volume for row in history]

        components = _compute_components(
            closes, volumes, today.date, config.mode, weights, sentiment_data
        )

        if components is None:
            # Not enough data; record equity and continue
            equity = cash + (position["shares"] * today.close if position else 0.0)
            equity_curve.append(EquityPoint(date=today.date, equity=equity))
            continue

        composite = components["composite"]
        direction = classify_direction(composite)
        strength = classify_strength(composite)
        strength_val = min_strength_order.get(strength, 0)

        # Check stop-loss / take-profit before signal logic
        if position is not None:
            pct_change = (
                (today.close - position["entry_price"]) / position["entry_price"] * 100
                if position["entry_price"] > 0
                else 0.0
            )
            trigger_exit = False
            exit_reason = None

            if config.stop_loss_pct is not None and pct_change <= -config.stop_loss_pct:
                trigger_exit = True
                exit_reason = "stop_loss"
            elif config.take_profit_pct is not None and pct_change >= config.take_profit_pct:
                trigger_exit = True
                exit_reason = "take_profit"

            if trigger_exit:
                effective_price = today.close * (1 - config.slippage_pct)
                gross_proceeds = position["shares"] * effective_price
                commission = gross_proceeds * config.commission_pct
                net_proceeds = gross_proceeds - commission
                rtn = (
                    ((net_proceeds - position["shares"] * position["entry_price"])
                     / (position["shares"] * position["entry_price"]) * 100)
                    if position["entry_price"] > 0
                    else 0.0
                )
                cash += net_proceeds
                equity = cash + 0.0  # position is about to be closed
                trades.append(
                    TradeRecord(
                        ticker=ticker,
                        action="sell",
                        trade_date=today.date,
                        price=today.close,
                        shares=position["shares"],
                        position_value=position["shares"] * today.close,
                        portfolio_equity=equity,
                        signal_score=round(composite, 5),
                        signal_direction=exit_reason,
                        signal_strength=exit_reason,
                        return_pct=round(rtn, 4),
                        exit_reason=exit_reason,
                    )
                )
                position = None
                equity_curve.append(EquityPoint(date=today.date, equity=equity))
                continue

        # Trading logic
        if position is None and direction == "bullish" and strength_val >= min_strength_val:
            # BUY: invest position_size_pct of cash
            if today.close > 0 and cash > 0:
                allocate = cash * (config.position_size_pct / 100.0)
                effective_price = today.close * (1 + config.slippage_pct)
                commission = allocate * config.commission_pct
                investable = allocate - commission
                shares = investable / effective_price
                position = {
                    "shares": shares,
                    "entry_price": effective_price,
                    "entry_date": today.date,
                }
                cash -= allocate
                position_value = shares * today.close
                equity = cash + position_value
                trades.append(
                    TradeRecord(
                        ticker=ticker,
                        action="buy",
                        trade_date=today.date,
                        price=today.close,
                        shares=shares,
                        position_value=position_value,
                        portfolio_equity=equity,
                        signal_score=round(composite, 5),
                        signal_direction=direction,
                        signal_strength=strength,
                    )
                )

        elif position is not None and direction == "bearish" and strength_val >= min_strength_val:
            # SELL: liquidate position
            effective_price = today.close * (1 - config.slippage_pct)
            gross_proceeds = position["shares"] * effective_price
            commission = gross_proceeds * config.commission_pct
            net_proceeds = gross_proceeds - commission
            return_pct = (
                ((net_proceeds - position["shares"] * position["entry_price"])
                 / (position["shares"] * position["entry_price"]) * 100)
                if position["entry_price"] > 0
                else 0.0
            )
            cash += net_proceeds
            equity = cash
            trades.append(
                TradeRecord(
                    ticker=ticker,
                    action="sell",
                    trade_date=today.date,
                    price=today.close,
                    shares=position["shares"],
                    position_value=position["shares"] * today.close,
                    portfolio_equity=equity,
                    signal_score=round(composite, 5),
                    signal_direction=direction,
                    signal_strength=strength,
                    return_pct=round(return_pct, 4),
                    exit_reason="signal",
                )
            )
            position = None

        # Record equity
        equity = cash + (position["shares"] * today.close if position else 0.0)
        equity_curve.append(EquityPoint(date=today.date, equity=equity))

    # Force-close any open position at end
    if position is not None and len(ohlcv) > 0:
        last_price = ohlcv[-1].close
        effective_price = last_price * (1 - config.slippage_pct)
        gross_proceeds = position["shares"] * effective_price
        commission = gross_proceeds * config.commission_pct
        net_proceeds = gross_proceeds - commission
        return_pct = (
            ((net_proceeds - position["shares"] * position["entry_price"])
             / (position["shares"] * position["entry_price"]) * 100)
            if position["entry_price"] > 0
            else 0.0
        )
        cash += net_proceeds
        trades.append(
            TradeRecord(
                ticker=ticker,
                action="sell",
                trade_date=ohlcv[-1].date,
                price=last_price,
                shares=position["shares"],
                position_value=position["shares"] * last_price,
                portfolio_equity=cash,
                signal_score=0.0,
                signal_direction="close",
                signal_strength="close",
                return_pct=round(return_pct, 4),
                exit_reason="end_of_period",
            )
        )
        # Update last equity point
        if equity_curve:
            equity_curve[-1] = EquityPoint(date=ohlcv[-1].date, equity=cash)

    metrics = compute_metrics(equity_curve, trades, config.starting_capital)

    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        **metrics,
    )


def _compute_components(
    closes: list[float],
    volumes: list[int],
    current_date: date,
    mode: str,
    weights: dict,
    sentiment_data: list[SentimentRow] | None,
) -> dict | None:
    """Compute weighted composite score from signal components."""
    # Technical components (always computed)
    price_mom = compute_price_momentum_from_closes(closes[-6:]) if len(closes) >= 6 else None
    vol_anomaly = (
        compute_volume_anomaly_from_data(closes[-21:], volumes[-21:])
        if len(closes) >= 21
        else None
    )
    rsi = compute_rsi_score_from_closes(closes[-RSI_LOOKBACK:]) if len(closes) >= RSI_LOOKBACK else None
    trend = (
        compute_trend_score_from_closes(closes[-TREND_LOOKBACK:])
        if len(closes) >= TREND_LOOKBACK
        else None
    )

    if mode == "technical":
        # Need at least one component
        pm = price_mom if price_mom is not None else 0.0
        va = vol_anomaly if vol_anomaly is not None else 0.0
        rv = rsi if rsi is not None else 0.0
        tv = trend if trend is not None else 0.0

        if price_mom is None and vol_anomaly is None and rsi is None and trend is None:
            return None

        composite = (
            weights.get("price_momentum", 0.30) * pm
            + weights.get("volume_anomaly", 0.20) * va
            + weights.get("rsi", 0.30) * rv
            + weights.get("trend", 0.20) * tv
        )

        return {"composite": composite}

    else:
        # Full mode: include sentiment
        sent_mom = None
        sent_vol = None
        if sentiment_data:
            sent_mom = compute_sentiment_momentum_from_data(sentiment_data, current_date)
            sent_vol = compute_sentiment_volume_from_data(sentiment_data, current_date)

        sm = sent_mom if sent_mom is not None else 0.0
        sv = sent_vol if sent_vol is not None else 0.0
        pm = price_mom if price_mom is not None else 0.0
        va = vol_anomaly if vol_anomaly is not None else 0.0
        rv = rsi if rsi is not None else 0.0
        tv = trend if trend is not None else 0.0

        has_sentiment = sent_mom is not None
        has_market = price_mom is not None

        if not has_sentiment and not has_market:
            return None

        composite = (
            weights.get("sentiment_momentum", 0.30) * sm
            + weights.get("sentiment_volume", 0.20) * sv
            + weights.get("price_momentum", 0.15) * pm
            + weights.get("volume_anomaly", 0.10) * va
            + weights.get("rsi", 0.15) * rv
            + weights.get("trend", 0.10) * tv
        )

        return {"composite": composite}


# ── Metrics computation ──


def compute_metrics(
    equity_curve: list[EquityPoint],
    trades: list[TradeRecord],
    starting_capital: float,
) -> dict:
    """Compute performance metrics from equity curve and trade log."""
    if not equity_curve:
        return _empty_metrics(starting_capital)

    final_equity = equity_curve[-1].equity

    # Total return
    total_return_pct = ((final_equity - starting_capital) / starting_capital) * 100

    # Annualized return
    trading_days = len(equity_curve)
    if trading_days > 1 and final_equity > 0 and starting_capital > 0:
        ratio = final_equity / starting_capital
        if ratio > 0:
            annualized_return_pct = (ratio ** (252 / trading_days) - 1) * 100
        else:
            annualized_return_pct = -100.0
    else:
        annualized_return_pct = 0.0

    # Sharpe ratio (annualized)
    sharpe_ratio = _compute_sharpe(equity_curve)

    # Max drawdown
    max_drawdown_pct = _compute_max_drawdown(equity_curve)

    # Trade statistics
    sell_trades = [t for t in trades if t.action == "sell" and t.return_pct is not None]
    total_trades = len(sell_trades)

    if total_trades > 0:
        wins = [t for t in sell_trades if t.return_pct is not None and t.return_pct > 0]
        losses = [t for t in sell_trades if t.return_pct is not None and t.return_pct <= 0]

        win_rate_pct = (len(wins) / total_trades) * 100
        avg_win_pct = sum(t.return_pct for t in wins) / len(wins) if wins else None
        avg_loss_pct = sum(t.return_pct for t in losses) / len(losses) if losses else None

        all_returns = [t.return_pct for t in sell_trades if t.return_pct is not None]
        best_trade_pct = max(all_returns) if all_returns else None
        worst_trade_pct = min(all_returns) if all_returns else None
    else:
        win_rate_pct = None
        avg_win_pct = None
        avg_loss_pct = None
        best_trade_pct = None
        worst_trade_pct = None

    return {
        "total_return_pct": round(total_return_pct, 4),
        "annualized_return_pct": round(annualized_return_pct, 4),
        "sharpe_ratio": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "win_rate_pct": round(win_rate_pct, 4) if win_rate_pct is not None else None,
        "total_trades": total_trades,
        "avg_win_pct": round(avg_win_pct, 4) if avg_win_pct is not None else None,
        "avg_loss_pct": round(avg_loss_pct, 4) if avg_loss_pct is not None else None,
        "best_trade_pct": round(best_trade_pct, 4) if best_trade_pct is not None else None,
        "worst_trade_pct": round(worst_trade_pct, 4) if worst_trade_pct is not None else None,
        "final_equity": round(final_equity, 2),
    }


def _compute_sharpe(equity_curve: list[EquityPoint]) -> float | None:
    """Annualized Sharpe ratio from daily equity values (risk-free rate = 0)."""
    if len(equity_curve) < 2:
        return None

    equities = [p.equity for p in equity_curve]
    daily_returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]

    if len(daily_returns) < 2:
        return None

    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    std_return = math.sqrt(variance)

    if std_return == 0:
        return None

    return (mean_return / std_return) * math.sqrt(252)


def _compute_max_drawdown(equity_curve: list[EquityPoint]) -> float:
    """Largest peak-to-trough percentage drop in equity."""
    if not equity_curve:
        return 0.0

    peak = equity_curve[0].equity
    max_dd = 0.0

    for point in equity_curve:
        if point.equity > peak:
            peak = point.equity
        if peak > 0:
            dd = (peak - point.equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

    return max_dd


# ── Sector aggregation ──


def aggregate_backtest_results(
    results: list[tuple[str, BacktestResult]],
    starting_capital: float,
) -> BacktestResult:
    """Aggregate per-ticker backtest results into a single sector-level result.

    Args:
        results: List of (ticker, BacktestResult) tuples.
        starting_capital: Total starting capital across all tickers.

    Returns:
        Combined BacktestResult with merged equity curves and trade logs.
    """
    if not results:
        return _empty_result(starting_capital)

    # Merge all trades
    all_trades: list[TradeRecord] = []
    for _, result in results:
        all_trades.extend(result.trades)
    all_trades.sort(key=lambda t: t.trade_date)

    # Merge equity curves by date: sum equity across all tickers for each date
    date_equity: dict[date, float] = {}
    for _, result in results:
        for point in result.equity_curve:
            date_equity[point.date] = date_equity.get(point.date, 0.0) + point.equity

    sorted_dates = sorted(date_equity.keys())
    combined_curve = [EquityPoint(date=d, equity=date_equity[d]) for d in sorted_dates]

    metrics = compute_metrics(combined_curve, all_trades, starting_capital)

    return BacktestResult(
        equity_curve=combined_curve,
        trades=all_trades,
        **metrics,
    )


# ── Benchmark comparison ──


@dataclass
class BenchmarkResult:
    total_return_pct: float
    annualized_return_pct: float
    alpha: float
    beta: float | None
    equity_curve: list[EquityPoint]


def compute_benchmark(
    benchmark_ohlcv: list[OHLCVRow],
    backtest_equity_curve: list[EquityPoint],
    starting_capital: float,
) -> BenchmarkResult | None:
    """Compute benchmark returns, alpha, and beta.

    Args:
        benchmark_ohlcv: OHLCV for benchmark (e.g. SPY), oldest first.
        backtest_equity_curve: The strategy's equity curve.
        starting_capital: Starting capital for normalization.

    Returns:
        BenchmarkResult or None if insufficient data.
    """
    if not benchmark_ohlcv or len(backtest_equity_curve) < 2:
        return None

    # Build date→close map for benchmark
    bench_prices: dict[date, float] = {row.date: row.close for row in benchmark_ohlcv}

    # Filter to dates in backtest equity curve
    curve_dates = [p.date for p in backtest_equity_curve]
    start_date = curve_dates[0]
    end_date = curve_dates[-1]

    # Build benchmark equity curve normalized to starting_capital
    # Find first available benchmark price on or after start_date
    bench_start_price = None
    for d in curve_dates:
        if d in bench_prices and bench_prices[d] > 0:
            bench_start_price = bench_prices[d]
            break

    if bench_start_price is None:
        return None

    bench_curve: list[EquityPoint] = []
    for d in curve_dates:
        if d in bench_prices and bench_prices[d] > 0:
            normalized = (bench_prices[d] / bench_start_price) * starting_capital
            bench_curve.append(EquityPoint(date=d, equity=round(normalized, 2)))

    if len(bench_curve) < 2:
        return None

    # Compute benchmark returns
    bench_final = bench_curve[-1].equity
    bench_total_return = ((bench_final - starting_capital) / starting_capital) * 100
    trading_days = len(bench_curve)
    ratio = bench_final / starting_capital
    if ratio > 0 and trading_days > 1:
        bench_annual_return = (ratio ** (252 / trading_days) - 1) * 100
    else:
        bench_annual_return = -100.0

    # Compute strategy annualized return for alpha
    strategy_final = backtest_equity_curve[-1].equity
    strategy_ratio = strategy_final / starting_capital
    strategy_days = len(backtest_equity_curve)
    if strategy_ratio > 0 and strategy_days > 1:
        strategy_annual = (strategy_ratio ** (252 / strategy_days) - 1) * 100
    else:
        strategy_annual = -100.0

    alpha = strategy_annual - bench_annual_return

    # Compute beta: Cov(strategy, benchmark) / Var(benchmark) using daily returns
    # Build aligned daily returns
    strategy_by_date = {p.date: p.equity for p in backtest_equity_curve}
    bench_by_date = {p.date: p.equity for p in bench_curve}
    common_dates = sorted(set(strategy_by_date.keys()) & set(bench_by_date.keys()))

    beta = None
    if len(common_dates) >= 3:
        strat_returns = []
        bench_returns = []
        for j in range(1, len(common_dates)):
            prev = common_dates[j - 1]
            curr = common_dates[j]
            sp = strategy_by_date[prev]
            sc = strategy_by_date[curr]
            bp = bench_by_date[prev]
            bc = bench_by_date[curr]
            if sp > 0 and bp > 0:
                strat_returns.append((sc - sp) / sp)
                bench_returns.append((bc - bp) / bp)

        if len(bench_returns) >= 2:
            mean_s = sum(strat_returns) / len(strat_returns)
            mean_b = sum(bench_returns) / len(bench_returns)
            cov = sum(
                (strat_returns[k] - mean_s) * (bench_returns[k] - mean_b)
                for k in range(len(strat_returns))
            ) / len(strat_returns)
            var_b = sum(
                (bench_returns[k] - mean_b) ** 2 for k in range(len(bench_returns))
            ) / len(bench_returns)
            if var_b > 0:
                beta = round(cov / var_b, 4)

    return BenchmarkResult(
        total_return_pct=round(bench_total_return, 4),
        annualized_return_pct=round(bench_annual_return, 4),
        alpha=round(alpha, 4),
        beta=beta,
        equity_curve=bench_curve,
    )


# ── Helpers ──


def _empty_result(starting_capital: float) -> BacktestResult:
    return BacktestResult(
        equity_curve=[],
        trades=[],
        total_return_pct=0.0,
        annualized_return_pct=0.0,
        sharpe_ratio=None,
        max_drawdown_pct=0.0,
        win_rate_pct=None,
        total_trades=0,
        avg_win_pct=None,
        avg_loss_pct=None,
        best_trade_pct=None,
        worst_trade_pct=None,
        final_equity=starting_capital,
    )


def _empty_metrics(starting_capital: float) -> dict:
    return {
        "total_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "sharpe_ratio": None,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": None,
        "total_trades": 0,
        "avg_win_pct": None,
        "avg_loss_pct": None,
        "best_trade_pct": None,
        "worst_trade_pct": None,
        "final_equity": starting_capital,
    }


def _date_offset(d: date, days: int) -> date:
    """Return a date offset by N days."""
    from datetime import timedelta

    return d + timedelta(days=days)
