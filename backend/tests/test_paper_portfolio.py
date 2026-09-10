"""Tests for Phase 22a paper portfolio helpers, beat schedule, and task guards."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

from worker.beat_schedule import beat_schedule
from worker.celery_app import celery_app
from worker.tasks.signals.paper_portfolio_task import snapshot_paper_portfolio, update_paper_portfolio
from worker.utils.paper_portfolio import (
    EXIT_SIGNAL_REVERSAL,
    EXIT_STOP_LOSS,
    EXIT_TAKE_PROFIT,
    OpenCandidate,
    close_reason,
    compute_portfolio_stats,
    decide_opens,
    is_weekday,
    meets_min_strength,
    position_shares,
    snapshot_returns,
)

SATURDAY = datetime(2026, 9, 12, 15, 35, tzinfo=UTC)


def _candidate(
    stock_id: int,
    *,
    sector_id: int | None = 1,
    strength: str = "moderate",
    close_price: float = 100.0,
    composite_score: float = 0.5,
    signal_id: int | None = None,
) -> OpenCandidate:
    return OpenCandidate(
        stock_id=stock_id,
        sector_id=sector_id,
        signal_id=signal_id if signal_id is not None else stock_id,
        strength=strength,
        close_price=close_price,
        composite_score=composite_score,
    )


def _decide(
    candidates: list[OpenCandidate],
    *,
    open_stock_ids: set[int] | None = None,
    sector_counts: dict[int | None, int] | None = None,
    cash: float = 100_000.0,
    portfolio_value: float = 100_000.0,
    max_positions: int = 10,
    max_per_sector: int = 3,
    position_size_pct: float = 0.10,
    min_strength: str = "moderate",
) -> list:
    return decide_opens(
        candidates,
        open_stock_ids=open_stock_ids or set(),
        sector_counts=sector_counts or {},
        cash=cash,
        portfolio_value=portfolio_value,
        max_positions=max_positions,
        max_per_sector=max_per_sector,
        position_size_pct=position_size_pct,
        min_strength=min_strength,
        stop_loss_pct=0.08,
        take_profit_pct=0.20,
    )


def _run_coro(coro):
    return asyncio.run(coro)


class TestCloseReason:
    def test_stop_loss_triggers_at_threshold(self):
        assert close_reason(100.0, 92.0, "bullish", 0.08, 0.20) == EXIT_STOP_LOSS

    def test_stop_loss_does_not_trigger_just_above(self):
        assert close_reason(100.0, 92.01, "bullish", 0.08, 0.20) is None

    def test_take_profit_triggers_at_threshold(self):
        assert close_reason(100.0, 120.0, "bullish", 0.08, 0.20) == EXIT_TAKE_PROFIT

    def test_signal_reversal_closes_non_bullish(self):
        assert close_reason(100.0, 101.0, "bearish", 0.08, 0.20) == EXIT_SIGNAL_REVERSAL
        assert close_reason(100.0, 101.0, "neutral", 0.08, 0.20) == EXIT_SIGNAL_REVERSAL

    def test_bullish_holds_inside_band(self):
        assert close_reason(100.0, 105.0, "bullish", 0.08, 0.20) is None

    def test_missing_signal_does_not_reverse(self):
        assert close_reason(100.0, 105.0, None, 0.08, 0.20) is None

    def test_stop_loss_wins_over_reversal(self):
        assert close_reason(100.0, 90.0, "bearish", 0.08, 0.20) == EXIT_STOP_LOSS


class TestDecideOpens:
    def test_opens_eligible_bullish(self):
        decisions = _decide([_candidate(1, close_price=100.0)])
        assert len(decisions) == 1
        assert decisions[0].stock_id == 1
        assert decisions[0].shares == 100
        assert decisions[0].cost == 10_000.0
        assert decisions[0].stop_loss_price == 92.0
        assert decisions[0].take_profit_price == 120.0

    def test_skips_existing_position(self):
        decisions = _decide([_candidate(1)], open_stock_ids={1})
        assert decisions == []

    def test_skips_weak_below_min_strength(self):
        decisions = _decide([_candidate(1, strength="weak")])
        assert decisions == []

    def test_respects_max_positions(self):
        candidates = [_candidate(i, composite_score=1.0 - i * 0.01) for i in range(1, 6)]
        decisions = _decide(candidates, open_stock_ids={10, 11}, max_positions=2)
        assert decisions == []

    def test_respects_sector_concentration(self):
        tech = [_candidate(i, sector_id=1, composite_score=0.9 - i * 0.01) for i in range(1, 4)]
        other = _candidate(99, sector_id=2, composite_score=0.4)
        decisions = _decide(tech + [other], sector_counts={1: 3})
        assert [d.stock_id for d in decisions] == [99]

    def test_skips_when_cash_below_position_size(self):
        decisions = _decide([_candidate(1)], cash=5_000.0, portfolio_value=100_000.0)
        assert decisions == []

    def test_ranks_by_composite_when_cash_allows_one(self):
        candidates = [
            _candidate(1, composite_score=0.4, close_price=100.0),
            _candidate(2, composite_score=0.9, close_price=100.0),
        ]
        decisions = _decide(candidates, cash=10_000.0, portfolio_value=100_000.0)
        assert [d.stock_id for d in decisions] == [2]


class TestSizingAndFilters:
    def test_position_shares_floors(self):
        assert position_shares(100_000.0, 0.10, 182.50) == 54

    def test_meets_min_strength(self):
        assert meets_min_strength("strong", "moderate")
        assert meets_min_strength("moderate", "moderate")
        assert not meets_min_strength("weak", "moderate")

    def test_is_weekday(self):
        assert is_weekday(0)
        assert is_weekday(4)
        assert not is_weekday(5)
        assert not is_weekday(6)


class TestSnapshotReturns:
    def test_cash_plus_equity_cumulative_and_benchmark(self):
        metrics = snapshot_returns(
            total_value=104_000.0,
            starting_capital=100_000.0,
            previous_total=100_000.0,
            spy_close=510.0,
            inception_spy=500.0,
        )
        assert metrics["cumulative_return_pct"] == 4.0
        assert metrics["daily_return_pct"] == 4.0
        assert metrics["benchmark_cumulative_return_pct"] == 2.0

    def test_first_snapshot_daily_return_zero(self):
        metrics = snapshot_returns(100_000.0, 100_000.0, None, 500.0, 500.0)
        assert metrics["daily_return_pct"] == 0.0
        assert metrics["cumulative_return_pct"] == 0.0
        assert metrics["benchmark_cumulative_return_pct"] == 0.0


class TestPortfolioStats:
    def test_sharpe_drawdown_win_rate_alpha_beta(self):
        total_values = [100.0, 102.0, 101.0]
        port = [0.02, -0.00980392156862745]
        bench = [0.01, -0.004901960784313725]
        trades = [8.2, 5.0, -2.0, 10.0]
        stats = compute_portfolio_stats(total_values, port, bench, trades)
        assert stats["sharpe_ratio"] is not None
        assert stats["max_drawdown_pct"] == round(1.0 / 102.0 * 100.0, 4)
        assert stats["win_rate_pct"] == 75.0
        assert stats["avg_win_pct"] == round((8.2 + 5.0 + 10.0) / 3, 4)
        assert stats["avg_loss_pct"] == -2.0
        assert stats["total_trades"] == 4
        assert stats["beta"] is not None
        assert abs(stats["beta"] - 2.0) < 1e-6
        assert stats["alpha"] is not None
        assert abs(stats["alpha"]) < 1e-6

    def test_empty_history(self):
        stats = compute_portfolio_stats([], [], [], [])
        assert stats["sharpe_ratio"] is None
        assert stats["max_drawdown_pct"] == 0.0
        assert stats["win_rate_pct"] is None
        assert stats["alpha"] is None
        assert stats["beta"] is None
        assert stats["total_trades"] == 0


class TestBeatAndInclude:
    def test_update_beat_at_minute_35_signals_queue(self):
        entry = beat_schedule["update-paper-portfolio"]
        assert entry["task"] == "worker.tasks.signals.paper_portfolio_task.update_paper_portfolio"
        assert entry["schedule"].minute == {35}
        assert entry["options"]["queue"] == "signals"

    def test_snapshot_beat_at_2130_utc(self):
        entry = beat_schedule["snapshot-paper-portfolio"]
        assert entry["task"] == "worker.tasks.signals.paper_portfolio_task.snapshot_paper_portfolio"
        assert entry["schedule"].hour == {21}
        assert entry["schedule"].minute == {30}
        assert entry["options"]["queue"] == "signals"

    def test_celery_includes_paper_portfolio_task(self):
        assert "worker.tasks.signals.paper_portfolio_task" in celery_app.conf.include


class TestTaskGuards:
    def test_update_skipped_when_disabled(self):
        with (
            patch("worker.tasks.signals.paper_portfolio_task.settings") as settings,
            patch("worker.utils.celery_helpers.run_async", side_effect=_run_coro),
        ):
            settings.paper_portfolio_enabled = False
            result = update_paper_portfolio.run()
        assert result == {"skipped": True, "reason": "disabled"}

    def test_snapshot_skipped_when_disabled(self):
        with (
            patch("worker.tasks.signals.paper_portfolio_task.settings") as settings,
            patch("worker.utils.celery_helpers.run_async", side_effect=_run_coro),
        ):
            settings.paper_portfolio_enabled = False
            result = snapshot_paper_portfolio.run()
        assert result == {"skipped": True, "reason": "disabled"}

    def test_update_skipped_on_weekend(self):
        class _FixedDateTime:
            @staticmethod
            def now(tz=None):
                return SATURDAY

        with (
            patch("worker.tasks.signals.paper_portfolio_task.settings") as settings,
            patch("worker.tasks.signals.paper_portfolio_task.datetime", _FixedDateTime),
            patch("worker.utils.celery_helpers.run_async", side_effect=_run_coro),
        ):
            settings.paper_portfolio_enabled = True
            result = update_paper_portfolio.run()
        assert result == {"skipped": True, "reason": "weekend"}
