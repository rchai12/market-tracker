"""Pure paper-portfolio decision helpers (no DB/Celery deps)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from worker.utils.performance_metrics import jensen_alpha_beta, max_drawdown_pct, sharpe_ratio

STRENGTH_RANK = {"weak": 0, "moderate": 1, "strong": 2}

EXIT_STOP_LOSS = "stop_loss"
EXIT_TAKE_PROFIT = "take_profit"
EXIT_SIGNAL_REVERSAL = "signal_reversal"


def is_weekday(weekday: int) -> bool:
    """True for Monday–Friday (datetime.weekday() 0–4)."""
    return 0 <= weekday <= 4


def meets_min_strength(strength: str, min_strength: str) -> bool:
    return STRENGTH_RANK.get(strength, -1) >= STRENGTH_RANK.get(min_strength, 1)


def close_reason(
    entry_price: float,
    current_price: float,
    signal_direction: str | None,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> str | None:
    """Return an exit reason, checking stop-loss then take-profit then reversal."""
    if entry_price <= 0 or current_price <= 0:
        return None
    if current_price <= entry_price * (1.0 - stop_loss_pct):
        return EXIT_STOP_LOSS
    if current_price >= entry_price * (1.0 + take_profit_pct):
        return EXIT_TAKE_PROFIT
    if signal_direction is not None and signal_direction != "bullish":
        return EXIT_SIGNAL_REVERSAL
    return None


def position_shares(portfolio_value: float, position_size_pct: float, close_price: float) -> int:
    if close_price <= 0 or portfolio_value <= 0 or position_size_pct <= 0:
        return 0
    return math.floor((portfolio_value * position_size_pct) / close_price)


def stop_loss_price(entry_price: float, stop_loss_pct: float) -> float:
    return entry_price * (1.0 - stop_loss_pct)


def take_profit_price(entry_price: float, take_profit_pct: float) -> float:
    return entry_price * (1.0 + take_profit_pct)


@dataclass(frozen=True)
class OpenCandidate:
    stock_id: int
    sector_id: int | None
    signal_id: int | None
    strength: str
    close_price: float
    composite_score: float


@dataclass(frozen=True)
class OpenDecision:
    stock_id: int
    signal_id: int | None
    shares: int
    entry_price: float
    cost: float
    stop_loss_price: float
    take_profit_price: float


def decide_opens(
    candidates: list[OpenCandidate],
    open_stock_ids: set[int],
    sector_counts: dict[int | None, int],
    cash: float,
    portfolio_value: float,
    max_positions: int,
    max_per_sector: int,
    position_size_pct: float,
    min_strength: str,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> list[OpenDecision]:
    """Pick new long entries, best composite first, respecting cash and concentration."""
    remaining_cash = cash
    current_count = len(open_stock_ids)
    held = set(open_stock_ids)
    counts = dict(sector_counts)
    opens: list[OpenDecision] = []
    min_cash_needed = position_size_pct * portfolio_value

    ranked = sorted(candidates, key=lambda c: c.composite_score, reverse=True)
    for candidate in ranked:
        if candidate.stock_id in held:
            continue
        if not meets_min_strength(candidate.strength, min_strength):
            continue
        if current_count >= max_positions:
            break
        if counts.get(candidate.sector_id, 0) >= max_per_sector:
            continue
        if remaining_cash < min_cash_needed:
            continue
        shares = position_shares(portfolio_value, position_size_pct, candidate.close_price)
        if shares < 1:
            continue
        cost = shares * candidate.close_price
        if remaining_cash < cost:
            continue
        opens.append(
            OpenDecision(
                stock_id=candidate.stock_id,
                signal_id=candidate.signal_id,
                shares=shares,
                entry_price=candidate.close_price,
                cost=cost,
                stop_loss_price=stop_loss_price(candidate.close_price, stop_loss_pct),
                take_profit_price=take_profit_price(candidate.close_price, take_profit_pct),
            )
        )
        remaining_cash -= cost
        current_count += 1
        held.add(candidate.stock_id)
        counts[candidate.sector_id] = counts.get(candidate.sector_id, 0) + 1
    return opens


def snapshot_returns(
    total_value: float,
    starting_capital: float,
    previous_total: float | None,
    spy_close: float | None,
    inception_spy: float | None,
) -> dict[str, float | None]:
    cumulative = ((total_value - starting_capital) / starting_capital) if starting_capital else 0.0
    if previous_total and previous_total > 0:
        daily = (total_value - previous_total) / previous_total
    else:
        daily = 0.0
    bench_cum = None
    if spy_close is not None and inception_spy is not None and inception_spy > 0:
        bench_cum = (spy_close - inception_spy) / inception_spy
    return {
        "daily_return_pct": daily * 100.0,
        "cumulative_return_pct": cumulative * 100.0,
        "benchmark_cumulative_return_pct": None if bench_cum is None else bench_cum * 100.0,
    }


def compute_portfolio_stats(
    total_values: list[float],
    portfolio_daily_returns: list[float],
    benchmark_daily_returns: list[float],
    trade_return_pcts: list[float],
) -> dict:
    """Sharpe, max drawdown, win rate, avg win/loss, alpha, beta.

    ``portfolio_daily_returns`` / ``benchmark_daily_returns`` are decimals (0.01 = 1%).
    ``trade_return_pcts`` are percentages (1.5 = +1.5%).
    ``max_drawdown_pct`` is a positive peak-to-trough percent.
    Alpha is annualized Jensen alpha in percent (rf = 0), same as backtests.
    """
    sharpe = sharpe_ratio(portfolio_daily_returns)
    max_dd = max_drawdown_pct(total_values)
    wins = [r for r in trade_return_pcts if r > 0]
    losses = [r for r in trade_return_pcts if r <= 0]
    total_trades = len(trade_return_pcts)
    win_rate = (len(wins) / total_trades * 100.0) if total_trades else None
    avg_win = (sum(wins) / len(wins)) if wins else None
    avg_loss = (sum(losses) / len(losses)) if losses else None
    alpha, beta = jensen_alpha_beta(portfolio_daily_returns, benchmark_daily_returns)
    return {
        "sharpe_ratio": None if sharpe is None else round(sharpe, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "win_rate_pct": None if win_rate is None else round(win_rate, 4),
        "avg_win_pct": None if avg_win is None else round(avg_win, 4),
        "avg_loss_pct": None if avg_loss is None else round(avg_loss, 4),
        "alpha": None if alpha is None else round(alpha, 4),
        "beta": None if beta is None else round(beta, 4),
        "total_trades": total_trades,
    }
