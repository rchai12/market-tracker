"""Shared performance metrics for paper portfolio and backtests.

Alpha is Jensen's alpha with rf = 0, in percent:
    (mean(Rp) - beta * mean(Rb)) * 252 * 100
Beta is Cov(Rp, Rb) / Var(Rb) on aligned daily decimal returns.
Sharpe uses population std and annualizes with sqrt(252), rf = 0.
"""

from __future__ import annotations

import math
from typing import Sequence

TRADING_DAYS = 252


def daily_returns(values: Sequence[float]) -> list[float]:
    """Simple returns from a level series. Skips non-positive bases."""
    out: list[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev > 0:
            out.append((values[i] - prev) / prev)
    return out


def sharpe_ratio(returns: Sequence[float]) -> float | None:
    """Annualized Sharpe ratio (rf = 0). None if fewer than 2 returns or zero vol."""
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (mean / std) * math.sqrt(TRADING_DAYS)


def max_drawdown_pct(values: Sequence[float]) -> float:
    """Largest peak-to-trough drop as a positive percent."""
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for value in values:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
    return max_dd


def jensen_alpha_beta(
    port_returns: Sequence[float],
    bench_returns: Sequence[float],
) -> tuple[float | None, float | None]:
    """Jensen alpha (percent, rf=0) and beta from paired daily decimal returns."""
    n = min(len(port_returns), len(bench_returns))
    if n < 2:
        return None, None
    port = list(port_returns[:n])
    bench = list(bench_returns[:n])
    mean_p = sum(port) / n
    mean_b = sum(bench) / n
    cov = sum((port[i] - mean_p) * (bench[i] - mean_b) for i in range(n)) / n
    var_b = sum((bench[i] - mean_b) ** 2 for i in range(n)) / n
    if var_b <= 0:
        return None, None
    beta = cov / var_b
    alpha_pct = (mean_p - beta * mean_b) * TRADING_DAYS * 100.0
    return alpha_pct, beta
