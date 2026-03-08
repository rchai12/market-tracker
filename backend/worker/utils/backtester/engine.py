"""Core backtest simulation engine.

Takes pre-fetched OHLCV data (and optionally sentiment data), replays signal
generation day by day, simulates trades, and returns an equity curve with
performance metrics.

Two modes:
- "technical": Uses only OHLCV-derived components (price momentum, volume anomaly,
  RSI, trend). Works for full 30+ year historical range.
- "full": Uses all 6 components including sentiment momentum and sentiment volume.
  Limited to the period since sentiment scraping began.
"""

from datetime import date

from .metrics import compute_metrics
from .models import (
    RSI_LOOKBACK,
    TECHNICAL_WEIGHTS,
    TREND_LOOKBACK,
    WARMUP_DAYS,
    BacktestConfig,
    BacktestResult,
    DEFAULT_WEIGHTS,
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
