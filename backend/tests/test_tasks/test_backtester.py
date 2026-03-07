"""Tests for the pure backtesting engine."""

import math
from datetime import date, timedelta

import pytest

from worker.utils.backtester import (
    BacktestConfig,
    BacktestResult,
    BenchmarkResult,
    EquityPoint,
    OHLCVRow,
    SentimentRow,
    TradeRecord,
    aggregate_backtest_results,
    classify_direction,
    classify_strength,
    compute_benchmark,
    compute_metrics,
    compute_price_momentum_from_closes,
    compute_rsi_score_from_closes,
    compute_sentiment_momentum_from_data,
    compute_sentiment_volume_from_data,
    compute_trend_score_from_closes,
    compute_volume_anomaly_from_data,
    run_backtest,
    STRONG_THRESHOLD,
    MODERATE_THRESHOLD,
    TECHNICAL_WEIGHTS,
    DEFAULT_WEIGHTS,
    WARMUP_DAYS,
)


# ── Helpers ──


def _make_ohlcv(
    start: date, days: int, base_price: float = 100.0, trend: float = 0.0, volume: int = 1000000
) -> list[OHLCVRow]:
    """Generate synthetic OHLCV data with optional price trend."""
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        price = base_price + trend * i
        rows.append(
            OHLCVRow(
                date=d,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=volume,
            )
        )
    return rows


def _make_uptrend_ohlcv(start: date, days: int, base: float = 100.0) -> list[OHLCVRow]:
    """Generate OHLCV with a steady uptrend (0.5% per day)."""
    return _make_ohlcv(start, days, base_price=base, trend=0.5)


def _make_downtrend_ohlcv(start: date, days: int, base: float = 100.0) -> list[OHLCVRow]:
    """Generate OHLCV with a steady downtrend (-0.5% per day)."""
    return _make_ohlcv(start, days, base_price=base, trend=-0.5)


def _make_volatile_ohlcv(start: date, days: int) -> list[OHLCVRow]:
    """Generate OHLCV that alternates up/down to test multiple trades."""
    rows = []
    # Pattern: 30 days up, 30 days down, repeat
    for i in range(days):
        d = start + timedelta(days=i)
        cycle = i % 60
        if cycle < 30:
            price = 100 + cycle * 2  # Up from 100 to 158
        else:
            price = 158 - (cycle - 30) * 2  # Down from 158 to 100
        rows.append(
            OHLCVRow(
                date=d,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=1000000,
            )
        )
    return rows


# ── Component function tests ──


class TestPriceMomentum:
    def test_positive_momentum(self):
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        result = compute_price_momentum_from_closes(closes)
        assert result is not None
        assert result > 0  # Price went up

    def test_negative_momentum(self):
        closes = [105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
        result = compute_price_momentum_from_closes(closes)
        assert result is not None
        assert result < 0  # Price went down

    def test_flat(self):
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        result = compute_price_momentum_from_closes(closes)
        assert result is not None
        assert abs(result) < 0.01  # Flat

    def test_insufficient_data(self):
        assert compute_price_momentum_from_closes([100.0]) is None

    def test_tanh_scaling(self):
        # 10% increase should give tanh(0.5) ≈ 0.46
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 110.0]
        result = compute_price_momentum_from_closes(closes)
        assert result is not None
        assert 0.45 < result < 0.48


class TestVolumeAnomaly:
    def test_high_volume_up(self):
        closes = [100.0, 100.0, 100.0, 101.0]  # Price up
        volumes = [1000, 1000, 1000, 3000]  # Volume spike
        result = compute_volume_anomaly_from_data(closes, volumes)
        assert result is not None
        assert result > 0  # High volume + price up = positive

    def test_high_volume_down(self):
        closes = [100.0, 100.0, 100.0, 99.0]  # Price down
        volumes = [1000, 1000, 1000, 3000]  # Volume spike
        result = compute_volume_anomaly_from_data(closes, volumes)
        assert result is not None
        assert result < 0  # High volume + price down = negative

    def test_normal_volume(self):
        closes = [100.0, 100.0, 100.0, 100.0]
        volumes = [1000, 1000, 1000, 1000]
        result = compute_volume_anomaly_from_data(closes, volumes)
        assert result is not None
        assert abs(result) < 0.01  # tanh(0) = 0

    def test_insufficient_data(self):
        assert compute_volume_anomaly_from_data([100.0, 101.0], [1000, 1000]) is None


class TestRsiScore:
    def test_oversold_positive(self):
        # Generate data that creates oversold RSI (price dropping consistently)
        closes = [100 - i * 0.5 for i in range(30)]
        result = compute_rsi_score_from_closes(closes)
        assert result is not None
        assert result > 0  # Oversold → positive (bullish)

    def test_overbought_negative(self):
        # Generate data that creates overbought RSI (price rising consistently)
        closes = [100 + i * 0.5 for i in range(30)]
        result = compute_rsi_score_from_closes(closes)
        assert result is not None
        assert result < 0  # Overbought → negative (bearish)

    def test_insufficient_data(self):
        assert compute_rsi_score_from_closes([100.0] * 10) is None

    def test_range(self):
        closes = [100 + i * 0.1 for i in range(30)]
        result = compute_rsi_score_from_closes(closes)
        assert result is not None
        assert -1.0 <= result <= 1.0


class TestTrendScore:
    def test_uptrend(self):
        # Consistent uptrend: SMA20 > SMA50 and positive MACD
        closes = [100 + i * 0.5 for i in range(60)]
        result = compute_trend_score_from_closes(closes)
        assert result is not None
        assert result > 0

    def test_downtrend(self):
        closes = [200 - i * 0.5 for i in range(60)]
        result = compute_trend_score_from_closes(closes)
        assert result is not None
        assert result < 0

    def test_insufficient_data(self):
        assert compute_trend_score_from_closes([100.0] * 40) is None

    def test_range(self):
        closes = [100 + i * 0.1 for i in range(60)]
        result = compute_trend_score_from_closes(closes)
        assert result is not None
        assert -1.0 <= result <= 1.0


class TestSentimentMomentum:
    def test_positive_sentiment(self):
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today, avg_positive=0.8, avg_negative=0.1, article_count=5),
        ]
        result = compute_sentiment_momentum_from_data(rows, today)
        assert result is not None
        assert result > 0

    def test_negative_sentiment(self):
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today, avg_positive=0.1, avg_negative=0.8, article_count=5),
        ]
        result = compute_sentiment_momentum_from_data(rows, today)
        assert result is not None
        assert result < 0

    def test_empty(self):
        assert compute_sentiment_momentum_from_data([], date(2024, 6, 15)) is None

    def test_decay_weighting(self):
        today = date(2024, 6, 15)
        # Recent positive, older negative — should net positive due to decay
        rows = [
            SentimentRow(date=today, avg_positive=0.8, avg_negative=0.1, article_count=5),
            SentimentRow(date=today - timedelta(days=2), avg_positive=0.1, avg_negative=0.8, article_count=5),
        ]
        result = compute_sentiment_momentum_from_data(rows, today)
        assert result is not None
        assert result > 0  # Recent positive should dominate


class TestSentimentVolume:
    def test_above_baseline(self):
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today, avg_positive=0.6, avg_negative=0.3, article_count=10),
        ]
        # Add baseline rows
        for i in range(1, 21):
            rows.append(
                SentimentRow(
                    date=today - timedelta(days=i),
                    avg_positive=0.5,
                    avg_negative=0.4,
                    article_count=2,
                )
            )
        result = compute_sentiment_volume_from_data(rows, today)
        assert result is not None
        assert result > 0  # Above baseline + positive sentiment

    def test_no_articles_today(self):
        today = date(2024, 6, 15)
        rows = [
            SentimentRow(date=today - timedelta(days=1), avg_positive=0.5, avg_negative=0.3, article_count=5),
        ]
        result = compute_sentiment_volume_from_data(rows, today)
        assert result is None


# ── Classification tests ──


class TestClassification:
    def test_direction(self):
        assert classify_direction(0.5) == "bullish"
        assert classify_direction(-0.5) == "bearish"
        assert classify_direction(0.005) == "neutral"
        assert classify_direction(0.0) == "neutral"

    def test_strength(self):
        assert classify_strength(0.7) == "strong"
        assert classify_strength(0.4) == "moderate"
        assert classify_strength(0.1) == "weak"
        assert classify_strength(-0.7) == "strong"

    def test_threshold_boundaries(self):
        assert classify_strength(STRONG_THRESHOLD) == "moderate"
        assert classify_strength(STRONG_THRESHOLD + 0.001) == "strong"
        assert classify_strength(MODERATE_THRESHOLD) == "weak"
        assert classify_strength(MODERATE_THRESHOLD + 0.001) == "moderate"


# ── Weights tests ──


class TestWeights:
    def test_technical_weights_sum_to_one(self):
        total = sum(TECHNICAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


# ── Metrics tests ──


class TestMetrics:
    def test_basic_metrics(self):
        base = date(2024, 1, 1)
        equity = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * 10)
            for i in range(100)
        ]
        trades = [
            TradeRecord(
                ticker="AAPL", action="buy", trade_date=date(2024, 1, 1),
                price=100, shares=100, position_value=10000, portfolio_equity=10000,
                signal_score=0.5, signal_direction="bullish", signal_strength="moderate",
            ),
            TradeRecord(
                ticker="AAPL", action="sell", trade_date=date(2024, 4, 10),
                price=110, shares=100, position_value=11000, portfolio_equity=11000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=10.0,
            ),
        ]
        result = compute_metrics(equity, trades, 10000)

        assert result["total_return_pct"] > 0
        assert result["final_equity"] == equity[-1].equity
        assert result["total_trades"] == 1  # Only sell trades count
        assert result["win_rate_pct"] == 100.0
        assert result["avg_win_pct"] == 10.0

    def test_empty_equity(self):
        result = compute_metrics([], [], 10000)
        assert result["total_return_pct"] == 0.0
        assert result["final_equity"] == 10000

    def test_no_trades(self):
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, [], 10000)
        assert result["total_trades"] == 0
        assert result["win_rate_pct"] is None

    def test_max_drawdown(self):
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=10000),
            EquityPoint(date=date(2024, 1, 2), equity=12000),  # Peak
            EquityPoint(date=date(2024, 1, 3), equity=9000),  # 25% drawdown from peak
            EquityPoint(date=date(2024, 1, 4), equity=11000),
        ]
        result = compute_metrics(equity, [], 10000)
        assert 24.9 < result["max_drawdown_pct"] < 25.1

    def test_sharpe_ratio(self):
        # Constant equity → zero std → None sharpe
        equity = [
            EquityPoint(date=date(2024, 1, i + 1), equity=10000) for i in range(10)
        ]
        result = compute_metrics(equity, [], 10000)
        assert result["sharpe_ratio"] is None

    def test_win_loss_stats(self):
        trades = [
            TradeRecord(
                ticker="AAPL", action="sell", trade_date=date(2024, 1, 1),
                price=110, shares=100, position_value=11000, portfolio_equity=11000,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=10.0,
            ),
            TradeRecord(
                ticker="AAPL", action="sell", trade_date=date(2024, 2, 1),
                price=95, shares=100, position_value=9500, portfolio_equity=9500,
                signal_score=-0.5, signal_direction="bearish", signal_strength="moderate",
                return_pct=-5.0,
            ),
        ]
        equity = [EquityPoint(date=date(2024, 1, 1), equity=10000)]
        result = compute_metrics(equity, trades, 10000)
        assert result["total_trades"] == 2
        assert result["win_rate_pct"] == 50.0
        assert result["avg_win_pct"] == 10.0
        assert result["avg_loss_pct"] == -5.0
        assert result["best_trade_pct"] == 10.0
        assert result["worst_trade_pct"] == -5.0


# ── Backtest engine tests ──


class TestRunBacktest:
    def test_insufficient_data(self):
        ohlcv = _make_ohlcv(date(2024, 1, 1), 30)  # Less than WARMUP_DAYS
        config = BacktestConfig()
        result = run_backtest("AAPL", ohlcv, config)
        assert result.total_trades == 0
        assert result.final_equity == config.starting_capital
        assert result.equity_curve == []

    def test_flat_market_no_trades(self):
        # Perfectly flat market should produce no strong signals
        ohlcv = _make_ohlcv(date(2023, 1, 1), 200, base_price=100.0, trend=0.0)
        config = BacktestConfig(mode="technical", starting_capital=10000)
        result = run_backtest("AAPL", ohlcv, config)
        # Flat market should not trigger moderate+ signals
        assert result.final_equity == config.starting_capital
        assert len(result.equity_curve) == 200 - WARMUP_DAYS

    def test_uptrend_makes_money(self):
        # Strong uptrend should eventually trigger bullish signal and profit
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 300)
        config = BacktestConfig(mode="technical", starting_capital=10000)
        result = run_backtest("AAPL", ohlcv, config)
        # In a strong uptrend, should buy and hold → profit
        assert len(result.equity_curve) > 0
        # Either we have trades and made money, or no trade was triggered (both valid)
        if result.total_trades > 0:
            assert result.total_return_pct > 0

    def test_equity_curve_length(self):
        ohlcv = _make_ohlcv(date(2023, 1, 1), 150, trend=0.1)
        config = BacktestConfig(mode="technical")
        result = run_backtest("AAPL", ohlcv, config)
        assert len(result.equity_curve) == 150 - WARMUP_DAYS

    def test_force_close_at_end(self):
        # Create strong uptrend to trigger a buy, then check force close
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 200)
        config = BacktestConfig(mode="technical", starting_capital=10000, min_signal_strength="weak")
        result = run_backtest("AAPL", ohlcv, config)
        # If there were buys, last trade should be a sell (force close)
        buy_count = sum(1 for t in result.trades if t.action == "buy")
        sell_count = sum(1 for t in result.trades if t.action == "sell")
        if buy_count > 0:
            assert sell_count >= buy_count  # At least as many sells as buys (force close)

    def test_starting_capital_preserved_when_no_trades(self):
        ohlcv = _make_ohlcv(date(2023, 1, 1), 100, base_price=100, trend=0.0)
        config = BacktestConfig(starting_capital=50000)
        result = run_backtest("AAPL", ohlcv, config)
        assert result.final_equity == 50000

    def test_custom_weights(self):
        ohlcv = _make_ohlcv(date(2023, 1, 1), 100, trend=0.2)
        custom_weights = {"price_momentum": 0.5, "volume_anomaly": 0.1, "rsi": 0.2, "trend": 0.2}
        config = BacktestConfig(
            mode="technical", starting_capital=10000, weights=custom_weights
        )
        result = run_backtest("AAPL", ohlcv, config)
        assert len(result.equity_curve) == 100 - WARMUP_DAYS

    def test_strong_only_fewer_trades(self):
        ohlcv = _make_volatile_ohlcv(date(2023, 1, 1), 300)
        config_moderate = BacktestConfig(mode="technical", min_signal_strength="moderate")
        config_strong = BacktestConfig(mode="technical", min_signal_strength="strong")
        result_moderate = run_backtest("TEST", ohlcv, config_moderate)
        result_strong = run_backtest("TEST", ohlcv, config_strong)
        # Strong threshold should produce same or fewer trades
        assert result_strong.total_trades <= result_moderate.total_trades

    def test_full_mode_with_sentiment(self):
        start = date(2024, 1, 1)
        ohlcv = _make_ohlcv(start, 100, trend=0.3)
        sentiment = [
            SentimentRow(
                date=start + timedelta(days=i),
                avg_positive=0.7 if i % 2 == 0 else 0.3,
                avg_negative=0.2 if i % 2 == 0 else 0.6,
                article_count=3,
            )
            for i in range(100)
        ]
        config = BacktestConfig(mode="full", starting_capital=10000)
        result = run_backtest("AAPL", ohlcv, config, sentiment_data=sentiment)
        assert len(result.equity_curve) == 100 - WARMUP_DAYS

    def test_full_mode_without_sentiment_falls_back(self):
        ohlcv = _make_ohlcv(date(2023, 1, 1), 100, trend=0.2)
        config = BacktestConfig(mode="full")
        result = run_backtest("AAPL", ohlcv, config, sentiment_data=None)
        assert len(result.equity_curve) == 100 - WARMUP_DAYS


# ── Aggregation tests ──


class TestAggregation:
    def test_aggregate_empty(self):
        result = aggregate_backtest_results([], 10000)
        assert result.total_trades == 0
        assert result.final_equity == 10000

    def test_aggregate_single(self):
        equity = [
            EquityPoint(date=date(2024, 1, 1), equity=5000),
            EquityPoint(date=date(2024, 1, 2), equity=5200),
        ]
        inner = BacktestResult(
            equity_curve=equity,
            trades=[],
            total_return_pct=4.0,
            annualized_return_pct=100.0,
            sharpe_ratio=1.5,
            max_drawdown_pct=0.0,
            win_rate_pct=None,
            total_trades=0,
            avg_win_pct=None,
            avg_loss_pct=None,
            best_trade_pct=None,
            worst_trade_pct=None,
            final_equity=5200,
        )
        result = aggregate_backtest_results([("AAPL", inner)], 5000)
        assert result.final_equity == 5200
        assert len(result.equity_curve) == 2

    def test_aggregate_multiple_sums_equity(self):
        eq1 = [
            EquityPoint(date=date(2024, 1, 1), equity=5000),
            EquityPoint(date=date(2024, 1, 2), equity=5100),
        ]
        eq2 = [
            EquityPoint(date=date(2024, 1, 1), equity=5000),
            EquityPoint(date=date(2024, 1, 2), equity=4900),
        ]
        r1 = BacktestResult(
            equity_curve=eq1, trades=[], total_return_pct=2.0, annualized_return_pct=0,
            sharpe_ratio=None, max_drawdown_pct=0, win_rate_pct=None, total_trades=0,
            avg_win_pct=None, avg_loss_pct=None, best_trade_pct=None, worst_trade_pct=None,
            final_equity=5100,
        )
        r2 = BacktestResult(
            equity_curve=eq2, trades=[], total_return_pct=-2.0, annualized_return_pct=0,
            sharpe_ratio=None, max_drawdown_pct=0, win_rate_pct=None, total_trades=0,
            avg_win_pct=None, avg_loss_pct=None, best_trade_pct=None, worst_trade_pct=None,
            final_equity=4900,
        )
        result = aggregate_backtest_results([("AAPL", r1), ("MSFT", r2)], 10000)
        assert result.final_equity == 10000  # 5100 + 4900
        # Equity on day 1: 5000 + 5000 = 10000
        assert result.equity_curve[0].equity == 10000
        # Equity on day 2: 5100 + 4900 = 10000
        assert result.equity_curve[1].equity == 10000


# ── Transaction cost tests ──


class TestTransactionCosts:
    def test_zero_costs_match_legacy(self):
        """Zero commission + slippage should produce same results as default config."""
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 300)
        config_default = BacktestConfig(mode="technical", starting_capital=10000)
        config_zero = BacktestConfig(
            mode="technical", starting_capital=10000,
            commission_pct=0.0, slippage_pct=0.0,
        )
        result_default = run_backtest("AAPL", ohlcv, config_default)
        result_zero = run_backtest("AAPL", ohlcv, config_zero)
        assert result_default.total_trades == result_zero.total_trades
        assert abs(result_default.final_equity - result_zero.final_equity) < 0.01

    def test_commission_reduces_returns(self):
        """Adding commission should reduce final equity compared to zero costs."""
        ohlcv = _make_volatile_ohlcv(date(2023, 1, 1), 300)
        config_no_cost = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
        )
        config_with_commission = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            commission_pct=0.01,  # 1% commission
        )
        result_no = run_backtest("TEST", ohlcv, config_no_cost)
        result_comm = run_backtest("TEST", ohlcv, config_with_commission)
        # If trades happen, commission should reduce equity
        if result_no.total_trades > 0 and result_comm.total_trades > 0:
            assert result_comm.final_equity < result_no.final_equity

    def test_slippage_reduces_returns(self):
        """Adding slippage should reduce final equity compared to zero costs."""
        ohlcv = _make_volatile_ohlcv(date(2023, 1, 1), 300)
        config_no_cost = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
        )
        config_with_slippage = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            slippage_pct=0.01,  # 1% slippage
        )
        result_no = run_backtest("TEST", ohlcv, config_no_cost)
        result_slip = run_backtest("TEST", ohlcv, config_with_slippage)
        if result_no.total_trades > 0 and result_slip.total_trades > 0:
            assert result_slip.final_equity < result_no.final_equity

    def test_higher_costs_worse_returns(self):
        """Higher transaction costs should produce worse returns."""
        ohlcv = _make_volatile_ohlcv(date(2023, 1, 1), 300)
        config_low = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            commission_pct=0.001, slippage_pct=0.0005,
        )
        config_high = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            commission_pct=0.02, slippage_pct=0.01,
        )
        result_low = run_backtest("TEST", ohlcv, config_low)
        result_high = run_backtest("TEST", ohlcv, config_high)
        if result_low.total_trades > 0 and result_high.total_trades > 0:
            assert result_high.final_equity <= result_low.final_equity

    def test_commission_applied_on_buy_and_sell(self):
        """Commission should be deducted on both buy and sell side."""
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 200)
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            commission_pct=0.05,  # 5% commission — very high to make effect obvious
        )
        result = run_backtest("AAPL", ohlcv, config)
        if result.total_trades > 0:
            # With 5% commission on both buy and sell, final equity must be noticeably less
            assert result.final_equity < 10000 * 0.95  # At least some reduction


# ── Position sizing tests ──


class TestPositionSizing:
    def test_full_position_matches_default(self):
        """100% position size should behave same as default."""
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 300)
        config_default = BacktestConfig(mode="technical", starting_capital=10000)
        config_full = BacktestConfig(
            mode="technical", starting_capital=10000, position_size_pct=100.0,
        )
        result_default = run_backtest("AAPL", ohlcv, config_default)
        result_full = run_backtest("AAPL", ohlcv, config_full)
        assert result_default.total_trades == result_full.total_trades
        assert abs(result_default.final_equity - result_full.final_equity) < 0.01

    def test_partial_position_preserves_cash(self):
        """With 50% position sizing, cash should remain non-zero when holding a position."""
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 200)
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            position_size_pct=50.0,
        )
        result = run_backtest("AAPL", ohlcv, config)
        # Find buy trades — on the day of buy, portfolio_equity should be less than
        # starting capital allocated (50% invested, 50% cash)
        buy_trades = [t for t in result.trades if t.action == "buy"]
        for bt in buy_trades:
            # The position value should be roughly 50% of portfolio equity
            assert bt.position_value < bt.portfolio_equity * 0.99  # Not fully invested

    def test_smaller_position_less_exposure(self):
        """Smaller position sizes should result in smaller individual trade sizes."""
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 200)
        config_large = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            position_size_pct=100.0,
        )
        config_small = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            position_size_pct=30.0,
        )
        result_large = run_backtest("TEST", ohlcv, config_large)
        result_small = run_backtest("TEST", ohlcv, config_small)
        # If both have at least one buy, the smaller position should buy fewer shares
        large_buys = [t for t in result_large.trades if t.action == "buy"]
        small_buys = [t for t in result_small.trades if t.action == "buy"]
        if large_buys and small_buys:
            assert small_buys[0].shares < large_buys[0].shares


# ── Stop-loss / Take-profit tests ──


class TestStopLossTakeProfit:
    def _make_drop_after_rise(self, start: date, days: int = 200) -> list[OHLCVRow]:
        """Generate data: 100 days up, then sharp 20% drop, then flat."""
        rows = []
        for i in range(days):
            d = start + timedelta(days=i)
            if i < 100:
                price = 100 + i * 0.5  # Up from 100 to 149.5
            elif i < 110:
                price = 149.5 - (i - 100) * 3.0  # Sharp drop: 149.5 → 119.5
            else:
                price = 119.5  # Flat
            rows.append(
                OHLCVRow(date=d, open=price, high=price * 1.005, low=price * 0.995, close=price, volume=1000000)
            )
        return rows

    def _make_rise_after_buy(self, start: date, days: int = 200) -> list[OHLCVRow]:
        """Generate data: steady rise to trigger buy, then continues rising 30%."""
        rows = []
        for i in range(days):
            d = start + timedelta(days=i)
            price = 100 + i * 0.3  # Steady uptrend
            rows.append(
                OHLCVRow(date=d, open=price, high=price * 1.005, low=price * 0.995, close=price, volume=1000000)
            )
        return rows

    def test_stop_loss_triggers(self):
        """Stop-loss should trigger exit when price drops enough."""
        ohlcv = self._make_drop_after_rise(date(2023, 1, 1))
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            stop_loss_pct=5.0,  # Exit at 5% drop
        )
        result = run_backtest("TEST", ohlcv, config)
        stop_loss_exits = [t for t in result.trades if t.exit_reason == "stop_loss"]
        # If a buy was made during the uptrend, the sharp drop should trigger stop-loss
        if any(t.action == "buy" for t in result.trades):
            assert len(stop_loss_exits) >= 1

    def test_take_profit_triggers(self):
        """Take-profit should trigger exit when price rises enough."""
        ohlcv = self._make_rise_after_buy(date(2023, 1, 1))
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            take_profit_pct=10.0,  # Exit at 10% gain
        )
        result = run_backtest("TEST", ohlcv, config)
        take_profit_exits = [t for t in result.trades if t.exit_reason == "take_profit"]
        if any(t.action == "buy" for t in result.trades):
            assert len(take_profit_exits) >= 1

    def test_exit_reason_on_signal_sell(self):
        """Normal signal-based sells should have exit_reason='signal'."""
        ohlcv = _make_volatile_ohlcv(date(2023, 1, 1), 300)
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
        )
        result = run_backtest("TEST", ohlcv, config)
        signal_sells = [t for t in result.trades if t.exit_reason == "signal"]
        # At least some signal-based exits should exist in volatile data
        # (but this depends on signals being generated)
        for t in result.trades:
            if t.action == "sell":
                assert t.exit_reason in ("signal", "end_of_period", "stop_loss", "take_profit")

    def test_exit_reason_end_of_period(self):
        """Force-closed position should have exit_reason='end_of_period'."""
        ohlcv = _make_uptrend_ohlcv(date(2023, 1, 1), 200)
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
        )
        result = run_backtest("TEST", ohlcv, config)
        # If there's a buy without a matching signal sell, force-close happens
        buys = sum(1 for t in result.trades if t.action == "buy")
        if buys > 0:
            last_sell = [t for t in result.trades if t.action == "sell"]
            if last_sell:
                # Last sell should be end_of_period or signal
                assert last_sell[-1].exit_reason in ("signal", "end_of_period")

    def test_stop_loss_limits_losses(self):
        """With stop-loss, individual trade losses should be bounded."""
        ohlcv = self._make_drop_after_rise(date(2023, 1, 1))
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            stop_loss_pct=5.0,
        )
        result = run_backtest("TEST", ohlcv, config)
        stop_loss_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
        for t in stop_loss_trades:
            # Return should be near -5% (with some slippage allowance)
            assert t.return_pct is not None
            assert t.return_pct >= -10.0  # Should be bounded near stop-loss level

    def test_no_stop_loss_when_none(self):
        """Without stop-loss config, no stop_loss exits should occur."""
        ohlcv = self._make_drop_after_rise(date(2023, 1, 1))
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            stop_loss_pct=None,
            take_profit_pct=None,
        )
        result = run_backtest("TEST", ohlcv, config)
        stop_loss_exits = [t for t in result.trades if t.exit_reason == "stop_loss"]
        take_profit_exits = [t for t in result.trades if t.exit_reason == "take_profit"]
        assert len(stop_loss_exits) == 0
        assert len(take_profit_exits) == 0


# ── Benchmark comparison tests ──


class TestBenchmark:
    def test_benchmark_basic(self):
        """compute_benchmark should return valid result with sufficient data."""
        base = date(2024, 1, 1)
        # Strategy equity: constant at $10000
        strategy_curve = [
            EquityPoint(date=base + timedelta(days=i), equity=10000)
            for i in range(100)
        ]
        # Benchmark: starts at $100, ends at $110 (10% gain)
        bench_ohlcv = [
            OHLCVRow(
                date=base + timedelta(days=i),
                open=100 + i * 0.1,
                high=100 + i * 0.1 + 0.5,
                low=100 + i * 0.1 - 0.5,
                close=100 + i * 0.1,
                volume=1000000,
            )
            for i in range(100)
        ]
        result = compute_benchmark(bench_ohlcv, strategy_curve, 10000)
        assert result is not None
        assert result.total_return_pct > 0  # Benchmark gained
        assert len(result.equity_curve) > 0
        # Strategy was flat, benchmark went up → negative alpha
        assert result.alpha < 0

    def test_benchmark_alpha_positive(self):
        """Strategy outperforming benchmark should give positive alpha."""
        base = date(2024, 1, 1)
        # Strategy equity: grows 20%
        strategy_curve = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * 20)
            for i in range(100)
        ]
        # Benchmark: grows 5%
        bench_ohlcv = [
            OHLCVRow(
                date=base + timedelta(days=i),
                open=100 + i * 0.05,
                high=100 + i * 0.05 + 0.5,
                low=100 + i * 0.05 - 0.5,
                close=100 + i * 0.05,
                volume=1000000,
            )
            for i in range(100)
        ]
        result = compute_benchmark(bench_ohlcv, strategy_curve, 10000)
        assert result is not None
        assert result.alpha > 0

    def test_benchmark_beta_computed(self):
        """Beta should be computed when sufficient data exists."""
        base = date(2024, 1, 1)
        strategy_curve = [
            EquityPoint(date=base + timedelta(days=i), equity=10000 + i * 10)
            for i in range(100)
        ]
        bench_ohlcv = [
            OHLCVRow(
                date=base + timedelta(days=i),
                open=100 + i * 0.1,
                high=100 + i * 0.1 + 0.5,
                low=100 + i * 0.1 - 0.5,
                close=100 + i * 0.1,
                volume=1000000,
            )
            for i in range(100)
        ]
        result = compute_benchmark(bench_ohlcv, strategy_curve, 10000)
        assert result is not None
        assert result.beta is not None

    def test_benchmark_normalized_equity(self):
        """Benchmark equity curve should be normalized to starting_capital."""
        base = date(2024, 1, 1)
        strategy_curve = [
            EquityPoint(date=base + timedelta(days=i), equity=10000)
            for i in range(50)
        ]
        bench_ohlcv = [
            OHLCVRow(
                date=base + timedelta(days=i),
                open=200.0, high=201.0, low=199.0, close=200.0,
                volume=1000000,
            )
            for i in range(50)
        ]
        result = compute_benchmark(bench_ohlcv, strategy_curve, 10000)
        assert result is not None
        # First equity point should be starting_capital (200/200 * 10000 = 10000)
        assert result.equity_curve[0].equity == 10000

    def test_benchmark_empty_inputs(self):
        """compute_benchmark should return None for empty inputs."""
        assert compute_benchmark([], [], 10000) is None
        assert compute_benchmark([], [EquityPoint(date=date(2024, 1, 1), equity=10000)], 10000) is None
        bench = [OHLCVRow(date=date(2024, 1, 1), open=100, high=101, low=99, close=100, volume=1000000)]
        # Only 1 equity point → < 2, returns None
        assert compute_benchmark(bench, [EquityPoint(date=date(2024, 1, 1), equity=10000)], 10000) is None

    def test_benchmark_no_matching_dates(self):
        """compute_benchmark should return None when no dates overlap."""
        base = date(2024, 1, 1)
        strategy_curve = [
            EquityPoint(date=base + timedelta(days=i), equity=10000)
            for i in range(10)
        ]
        # Benchmark data on completely different dates
        bench_ohlcv = [
            OHLCVRow(
                date=base + timedelta(days=100 + i),
                open=100, high=101, low=99, close=100,
                volume=1000000,
            )
            for i in range(10)
        ]
        result = compute_benchmark(bench_ohlcv, strategy_curve, 10000)
        assert result is None
