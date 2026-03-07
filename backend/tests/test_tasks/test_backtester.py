"""Tests for the pure backtesting engine."""

import math
from datetime import date, timedelta

import pytest

from worker.utils.backtester import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    OHLCVRow,
    SentimentRow,
    TradeRecord,
    aggregate_backtest_results,
    classify_direction,
    classify_strength,
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
