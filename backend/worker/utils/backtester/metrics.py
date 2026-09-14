"""Performance metrics computation for backtesting results."""

from worker.utils.performance_metrics import daily_returns, max_drawdown_pct, sharpe_ratio

from .models import EquityPoint, TradeRecord


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
    return sharpe_ratio(daily_returns([p.equity for p in equity_curve]))


def _compute_max_drawdown(equity_curve: list[EquityPoint]) -> float:
    """Largest peak-to-trough percentage drop in equity."""
    return max_drawdown_pct([p.equity for p in equity_curve])


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
