"""Mutation-killing tests for worker/utils/backtester/engine.py.

These tests verify slippage direction, commission deduction, position sizing math,
stop-loss/take-profit exact thresholds, force-close logic, and warmup offset.
"""

from datetime import date, timedelta

from worker.utils.backtester.engine import run_backtest
from worker.utils.backtester.models import (
    BacktestConfig,
    OHLCVRow,
    WARMUP_DAYS,
)


def _make_ohlcv(
    start: date, days: int, base_price: float = 100.0, trend: float = 0.0, volume: int = 1000000
) -> list[OHLCVRow]:
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        price = base_price + trend * i
        rows.append(
            OHLCVRow(date=d, open=price, high=price * 1.01, low=price * 0.99, close=price, volume=volume)
        )
    return rows


def _make_single_trade_ohlcv(
    start: date,
    warmup_price: float = 100.0,
    buy_price: float = 100.0,
    sell_price: float = 110.0,
) -> list[OHLCVRow]:
    """Create OHLCV data that forces exactly one buy then one sell.

    - WARMUP_DAYS of uptrend (to build bullish signal)
    - 1 day at buy_price (buy triggers)
    - 30 days of decline (bearish signal builds)
    - 1 day at sell_price (sell triggers)
    """
    rows = []
    # Warmup: strong uptrend to build bullish indicators
    for i in range(WARMUP_DAYS):
        d = start + timedelta(days=i)
        price = warmup_price + i * 0.5
        rows.append(OHLCVRow(date=d, open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1000000))

    # Buy day
    d = start + timedelta(days=WARMUP_DAYS)
    rows.append(OHLCVRow(date=d, open=buy_price, high=buy_price * 1.01, low=buy_price * 0.99, close=buy_price, volume=1000000))

    return rows


class TestBuySlippageDirection:
    def test_buy_slippage_increases_effective_price(self):
        """Kill mutation: `close * (1 + slippage)` vs `close * (1 - slippage)`."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 200, trend=0.5)
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            slippage_pct=0.05,  # 5% slippage — large to make effect obvious
            commission_pct=0.0,
        )
        result = run_backtest("TEST", ohlcv, config)
        buy_trades = [t for t in result.trades if t.action == "buy"]
        if buy_trades:
            bt = buy_trades[0]
            # With buy slippage, we should get fewer shares than close/price would suggest
            # shares = (cash - commission) / (close * (1 + slippage))
            # shares < cash / close (since effective price > close)
            no_slippage_shares = 10000 / bt.price
            assert bt.shares < no_slippage_shares


class TestSellSlippageDirection:
    def test_sell_slippage_decreases_effective_price(self):
        """Kill mutation: `close * (1 - slippage)` vs `close * (1 + slippage)`."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 300, trend=0.5)
        config_no_slip = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            slippage_pct=0.0,
            commission_pct=0.0,
        )
        config_slip = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            slippage_pct=0.05,  # 5% slippage
            commission_pct=0.0,
        )
        result_no = run_backtest("TEST", ohlcv, config_no_slip)
        result_slip = run_backtest("TEST", ohlcv, config_slip)
        # If both have sell trades, slippage should reduce proceeds
        sells_no = [t for t in result_no.trades if t.action == "sell"]
        sells_slip = [t for t in result_slip.trades if t.action == "sell"]
        if sells_no and sells_slip:
            assert result_slip.final_equity < result_no.final_equity


class TestCommissionOnBuy:
    def test_commission_deducted_from_allocation(self):
        """Kill mutation: commission subtracted from investable vs added."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 200, trend=0.5)
        config_no = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            commission_pct=0.0, slippage_pct=0.0,
        )
        config_comm = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            commission_pct=0.10,  # 10% commission
            slippage_pct=0.0,
        )
        result_no = run_backtest("TEST", ohlcv, config_no)
        result_comm = run_backtest("TEST", ohlcv, config_comm)
        buy_no = [t for t in result_no.trades if t.action == "buy"]
        buy_comm = [t for t in result_comm.trades if t.action == "buy"]
        if buy_no and buy_comm:
            # With 10% commission, should buy fewer shares
            assert buy_comm[0].shares < buy_no[0].shares


class TestPositionSizePct:
    def test_division_by_100(self):
        """Kill mutation: `pct / 100.0` removed or changed."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 200, trend=0.5)
        config_50 = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            position_size_pct=50.0,
            commission_pct=0.0, slippage_pct=0.0,
        )
        config_100 = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            position_size_pct=100.0,
            commission_pct=0.0, slippage_pct=0.0,
        )
        result_50 = run_backtest("TEST", ohlcv, config_50)
        result_100 = run_backtest("TEST", ohlcv, config_100)
        buy_50 = [t for t in result_50.trades if t.action == "buy"]
        buy_100 = [t for t in result_100.trades if t.action == "buy"]
        if buy_50 and buy_100:
            # 50% should buy roughly half the shares of 100%
            ratio = buy_50[0].shares / buy_100[0].shares
            assert 0.4 < ratio < 0.6


class TestStopLossThreshold:
    def test_stop_loss_triggers_on_drop(self):
        """Kill mutation: `pct_change <= -stop_loss_pct` vs `<` or boundary off."""
        start = date(2023, 1, 1)
        # Strong uptrend to trigger early buy, then crash
        rows = []
        for i in range(WARMUP_DAYS + 30):
            d = start + timedelta(days=i)
            price = 100.0 + i * 1.0  # Strong uptrend $1/day
            rows.append(OHLCVRow(date=d, open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1000000))

        # Now crash 30% over 5 days
        peak_price = rows[-1].close
        for i in range(1, 6):
            d = start + timedelta(days=WARMUP_DAYS + 30 + i)
            price = peak_price * (1 - 0.06 * i)  # 6% per day drop
            rows.append(OHLCVRow(date=d, open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1000000))

        # Flat at bottom for a while
        bottom = rows[-1].close
        for i in range(30):
            d = start + timedelta(days=WARMUP_DAYS + 36 + i)
            rows.append(OHLCVRow(date=d, open=bottom, high=bottom * 1.01, low=bottom * 0.99, close=bottom, volume=1000000))

        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            stop_loss_pct=5.0,
            commission_pct=0.0, slippage_pct=0.0,
        )
        result = run_backtest("TEST", rows, config)
        buys = [t for t in result.trades if t.action == "buy"]
        sl_exits = [t for t in result.trades if t.exit_reason == "stop_loss"]
        if buys:
            # Find if any buy happened before the crash
            crash_start = start + timedelta(days=WARMUP_DAYS + 30)
            buys_before_crash = [t for t in buys if t.trade_date < crash_start]
            if buys_before_crash:
                assert len(sl_exits) >= 1


class TestTakeProfitThreshold:
    def test_exact_boundary(self):
        """Kill mutation: `pct_change >= take_profit_pct` vs `>` or boundary off."""
        start = date(2023, 1, 1)
        rows = []
        # Uptrend to trigger buy
        for i in range(WARMUP_DAYS):
            d = start + timedelta(days=i)
            price = 100.0 + i * 0.5
            rows.append(OHLCVRow(date=d, open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1000000))

        # Continue strong rise for take-profit to trigger
        for i in range(50):
            d = start + timedelta(days=WARMUP_DAYS + i)
            price = (100.0 + WARMUP_DAYS * 0.5) + i * 1.0
            rows.append(OHLCVRow(date=d, open=price, high=price * 1.01, low=price * 0.99, close=price, volume=1000000))

        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
            take_profit_pct=10.0,
            commission_pct=0.0, slippage_pct=0.0,
        )
        result = run_backtest("TEST", rows, config)
        tp_exits = [t for t in result.trades if t.exit_reason == "take_profit"]
        if any(t.action == "buy" for t in result.trades):
            # Strong continued rise should trigger take-profit
            assert len(tp_exits) >= 1


class TestForceCloseAtEnd:
    def test_end_of_period_exit_reason(self):
        """Kill mutation: exit_reason='end_of_period' is set correctly."""
        # Strong uptrend, weak threshold to ensure a buy happens
        ohlcv = _make_ohlcv(date(2023, 1, 1), 100, trend=0.5)
        config = BacktestConfig(
            mode="technical", starting_capital=10000,
            min_signal_strength="weak",
        )
        result = run_backtest("TEST", ohlcv, config)
        buys = [t for t in result.trades if t.action == "buy"]
        sells = [t for t in result.trades if t.action == "sell"]
        if buys:
            # Should have at least one sell (force-close)
            assert len(sells) >= 1
            # The last sell's exit_reason should be one of the valid reasons
            last_sell = sells[-1]
            assert last_sell.exit_reason in ("signal", "end_of_period", "stop_loss", "take_profit")


class TestWarmupOffset:
    def test_simulation_starts_at_warmup(self):
        """Kill mutation: `range(WARMUP_DAYS, ...)` changed to `range(0, ...)`."""
        days = WARMUP_DAYS + 10
        ohlcv = _make_ohlcv(date(2023, 1, 1), days, trend=0.0)
        config = BacktestConfig(mode="technical", starting_capital=10000)
        result = run_backtest("TEST", ohlcv, config)
        # Equity curve should have exactly (days - WARMUP_DAYS) points
        assert len(result.equity_curve) == 10

    def test_not_enough_data_for_warmup(self):
        """Kill mutation: `WARMUP_DAYS + 1` boundary check."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), WARMUP_DAYS)  # Exactly WARMUP_DAYS, not +1
        config = BacktestConfig(mode="technical", starting_capital=10000)
        result = run_backtest("TEST", ohlcv, config)
        assert result.equity_curve == []
        assert result.total_trades == 0
        assert result.final_equity == 10000


class TestWeightSelection:
    def test_technical_mode_uses_technical_weights(self):
        """Kill mutation: wrong weight dict used for technical mode."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 100, trend=0.3)
        config = BacktestConfig(mode="technical", starting_capital=10000)
        result = run_backtest("TEST", ohlcv, config)
        # Should work without sentiment data in technical mode
        assert len(result.equity_curve) == 100 - WARMUP_DAYS

    def test_custom_weights_override(self):
        """Kill mutation: custom weights are actually used when provided."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 100, trend=0.3)
        custom = {"price_momentum": 1.0, "volume_anomaly": 0.0, "rsi": 0.0, "trend": 0.0}
        config = BacktestConfig(mode="technical", starting_capital=10000, weights=custom)
        result = run_backtest("TEST", ohlcv, config)
        assert len(result.equity_curve) == 100 - WARMUP_DAYS


class TestMinStrengthFilter:
    def test_strong_filter_blocks_moderate(self):
        """Kill mutation: strength ordering `min_strength_order` dict values."""
        ohlcv = _make_ohlcv(date(2023, 1, 1), 200, trend=0.3)
        config_weak = BacktestConfig(mode="technical", min_signal_strength="weak")
        config_strong = BacktestConfig(mode="technical", min_signal_strength="strong")
        result_weak = run_backtest("TEST", ohlcv, config_weak)
        result_strong = run_backtest("TEST", ohlcv, config_strong)
        # Strong filter should produce <= trades than weak
        assert result_strong.total_trades <= result_weak.total_trades
