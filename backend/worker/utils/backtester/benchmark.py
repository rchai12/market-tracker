"""Benchmark comparison for backtesting results."""

from datetime import date

from worker.utils.performance_metrics import daily_returns, jensen_alpha_beta

from .models import BenchmarkResult, EquityPoint, OHLCVRow


def compute_benchmark(
    benchmark_ohlcv: list[OHLCVRow],
    backtest_equity_curve: list[EquityPoint],
    starting_capital: float,
) -> BenchmarkResult | None:
    """Compute benchmark returns plus Jensen alpha and beta (rf = 0)."""
    if not benchmark_ohlcv or len(backtest_equity_curve) < 2:
        return None

    bench_prices: dict[date, float] = {row.date: row.close for row in benchmark_ohlcv}
    curve_dates = [p.date for p in backtest_equity_curve]

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

    bench_final = bench_curve[-1].equity
    bench_total_return = ((bench_final - starting_capital) / starting_capital) * 100
    trading_days = len(bench_curve)
    ratio = bench_final / starting_capital
    if ratio > 0 and trading_days > 1:
        bench_annual_return = (ratio ** (252 / trading_days) - 1) * 100
    else:
        bench_annual_return = -100.0

    strategy_by_date = {p.date: p.equity for p in backtest_equity_curve}
    bench_by_date = {p.date: p.equity for p in bench_curve}
    common_dates = sorted(set(strategy_by_date.keys()) & set(bench_by_date.keys()))

    strat_levels = [strategy_by_date[d] for d in common_dates]
    bench_levels = [bench_by_date[d] for d in common_dates]
    alpha, beta = jensen_alpha_beta(daily_returns(strat_levels), daily_returns(bench_levels))

    return BenchmarkResult(
        total_return_pct=round(bench_total_return, 4),
        annualized_return_pct=round(bench_annual_return, 4),
        alpha=None if alpha is None else round(alpha, 4),
        beta=None if beta is None else round(beta, 4),
        equity_curve=bench_curve,
    )
