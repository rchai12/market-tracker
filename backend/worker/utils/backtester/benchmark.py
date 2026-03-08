"""Benchmark comparison for backtesting results."""

from datetime import date

from .models import BenchmarkResult, EquityPoint, OHLCVRow


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

    # Build date->close map for benchmark
    bench_prices: dict[date, float] = {row.date: row.close for row in benchmark_ohlcv}

    # Filter to dates in backtest equity curve
    curve_dates = [p.date for p in backtest_equity_curve]

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
