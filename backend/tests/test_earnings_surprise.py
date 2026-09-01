"""Tests for Phase 21b earnings surprise: yfinance fetch, scoring, and default weights."""

import asyncio
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from worker.beat_schedule import beat_schedule
from worker.tasks.scraping.earnings_data import _fetch_ticker, _safe_float
from worker.tasks.signals.component_scores import EARNINGS_WINDOW_DAYS, calc_earnings_surprise_score
from worker.tasks.signals.signal_generator import (
    WEIGHT_EARNINGS,
    WEIGHT_OPTIONS,
    _default_weights,
)

NOW = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)


def _hist_df(surprise=0.152, report="2026-08-30", estimate=1.00, actual=1.152):
    return pd.DataFrame(
        {
            "epsEstimate": [estimate],
            "epsActual": [actual],
            "surprisePercent": [surprise],
        },
        index=pd.to_datetime([report]),
    )


class _FakeInsert:
    excluded = MagicMock()

    def __init__(self):
        self.values_kwargs = None
        self.conflict = None

    def values(self, **kwargs):
        self.values_kwargs = kwargs
        return self

    def on_conflict_do_update(self, constraint=None, set_=None):
        self.conflict = {"constraint": constraint, "set": set_}
        return self


def _session_cm(session):
    class CM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    return CM


async def _run_fetch(ticker_obj, inserts: list[_FakeInsert]):
    session = AsyncMock()
    session.commit = AsyncMock()

    def _insert(_table):
        stmt = _FakeInsert()
        inserts.append(stmt)
        return stmt

    with (
        patch("worker.tasks.scraping.earnings_data.yf.Ticker", return_value=ticker_obj),
        patch("worker.tasks.scraping.earnings_data.async_session", _session_cm(session)),
        patch("worker.tasks.scraping.earnings_data.pg_insert", side_effect=_insert),
    ):
        count = await _fetch_ticker("AAPL", 7)
    return count, session


class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float(1.5) == 1.5

    def test_none(self):
        assert _safe_float(None) is None

    def test_nan(self):
        assert _safe_float(float("nan")) is None

    def test_invalid_string(self):
        assert _safe_float("abc") is None

    def test_zero(self):
        assert _safe_float(0) == 0.0


class TestFetchTicker:
    def test_history_upserts_reported_true(self):
        ticker = MagicMock()
        ticker.earnings_history = _hist_df()
        ticker.calendar = None
        inserts: list[_FakeInsert] = []

        count, _session = asyncio.run(_run_fetch(ticker, inserts))

        assert count == 1
        rec = inserts[0].values_kwargs
        assert rec["stock_id"] == 7
        assert rec["earnings_date"] == date(2026, 8, 30)
        assert rec["reported"] is True
        assert rec["estimated_eps"] == 1.00
        assert rec["actual_eps"] == 1.152

    def test_surprise_percent_converted_to_percentage(self):
        ticker = MagicMock()
        ticker.earnings_history = _hist_df(surprise=0.152)
        ticker.calendar = None
        inserts: list[_FakeInsert] = []

        asyncio.run(_run_fetch(ticker, inserts))

        assert inserts[0].values_kwargs["surprise_pct"] == 15.2

    def test_future_calendar_stored_unreported(self):
        ticker = MagicMock()
        ticker.earnings_history = pd.DataFrame()
        future = date.today() + timedelta(days=14)
        ticker.calendar = {
            "Earnings Date": [datetime(future.year, future.month, future.day)],
            "Earnings Average": 2.5,
            "Revenue Average": 1_000_000.0,
        }
        inserts: list[_FakeInsert] = []

        count, _session = asyncio.run(_run_fetch(ticker, inserts))

        assert count == 1
        rec = inserts[0].values_kwargs
        assert rec["reported"] is False
        assert rec["earnings_date"] == future
        assert rec["estimated_eps"] == 2.5
        assert rec["estimated_revenue"] == 1_000_000.0

    def test_past_calendar_date_skipped(self):
        ticker = MagicMock()
        ticker.earnings_history = pd.DataFrame()
        past = date.today() - timedelta(days=5)
        ticker.calendar = {
            "Earnings Date": [datetime(past.year, past.month, past.day)],
            "Earnings Average": 1.0,
        }
        inserts: list[_FakeInsert] = []

        count, _session = asyncio.run(_run_fetch(ticker, inserts))

        assert count == 0
        assert inserts == []

    def test_history_exception_still_fetches_calendar(self):
        class BoomTicker:
            @property
            def earnings_history(self):
                raise RuntimeError("unavailable")

            calendar = {
                "Earnings Date": [datetime.now() + timedelta(days=10)],
                "Earnings Average": 1.1,
            }

        inserts: list[_FakeInsert] = []
        count, _session = asyncio.run(_run_fetch(BoomTicker(), inserts))

        assert count == 1
        assert inserts[0].values_kwargs["reported"] is False

    def test_null_calendar_no_crash(self):
        ticker = MagicMock()
        ticker.earnings_history = pd.DataFrame()
        ticker.calendar = None
        inserts: list[_FakeInsert] = []

        count, _session = asyncio.run(_run_fetch(ticker, inserts))

        assert count == 0
        assert inserts == []

    def test_upsert_on_conflict_updates_without_duplicating(self):
        ticker = MagicMock()
        ticker.earnings_history = _hist_df()
        ticker.calendar = None
        inserts: list[_FakeInsert] = []

        count, session = asyncio.run(_run_fetch(ticker, inserts))

        assert count == 1
        assert inserts[0].conflict["constraint"] == "uq_earnings_stock_date"
        assert "fetched_at" in inserts[0].conflict["set"]
        session.execute.assert_awaited()
        session.commit.assert_awaited()


def _earnings(**overrides):
    base = dict(
        surprise_pct=15.2,
        guidance_change=None,
        reported=True,
        earnings_date=NOW.date(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _score_session(earnings_obj):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = earnings_obj
    session.execute = AsyncMock(return_value=result)
    return session


class TestCalcEarningsSurpriseScore:
    def test_beat_within_window_positive(self):
        score = asyncio.run(calc_earnings_surprise_score(_score_session(_earnings(surprise_pct=15.2)), 1, NOW))
        expected = math.tanh(15.2 / 5.0)
        assert score is not None
        assert score > 0
        assert abs(score - expected) < 1e-9

    def test_miss_within_window_negative(self):
        score = asyncio.run(calc_earnings_surprise_score(_score_session(_earnings(surprise_pct=-8.0)), 1, NOW))
        assert score is not None
        assert score < 0
        assert abs(score - math.tanh(-8.0 / 5.0)) < 1e-9

    def test_zero_surprise(self):
        score = asyncio.run(calc_earnings_surprise_score(_score_session(_earnings(surprise_pct=0.0)), 1, NOW))
        assert score == 0.0

    def test_three_days_ago_returns_none(self):
        session = _score_session(None)
        score = asyncio.run(calc_earnings_surprise_score(session, 1, NOW))
        assert score is None
        stmt = session.execute.call_args[0][0]
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        window_start = NOW.date() - timedelta(days=EARNINGS_WINDOW_DAYS)
        assert str(window_start) in sql
        assert str(NOW.date()) in sql

    def test_upcoming_unreported_excluded(self):
        session = _score_session(None)
        score = asyncio.run(calc_earnings_surprise_score(session, 1, NOW))
        assert score is None
        stmt = session.execute.call_args[0][0]
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        assert "reported" in sql

    def test_extreme_surprise_clamped_to_one(self):
        score = asyncio.run(calc_earnings_surprise_score(_score_session(_earnings(surprise_pct=100.0)), 1, NOW))
        assert score == 1.0

    def test_no_earnings_record_returns_none(self):
        score = asyncio.run(calc_earnings_surprise_score(_score_session(None), 1, NOW))
        assert score is None

    def test_guidance_raised_adds_boost_capped(self):
        score = asyncio.run(
            calc_earnings_surprise_score(
                _score_session(_earnings(surprise_pct=15.2, guidance_change="raised")), 1, NOW
            )
        )
        uncapped = math.tanh(15.2 / 5.0) + 0.2
        assert score is not None
        assert score == min(1.0, uncapped)
        assert score == 1.0

    def test_guidance_none_no_modifier(self):
        score = asyncio.run(
            calc_earnings_surprise_score(
                _score_session(_earnings(surprise_pct=5.0, guidance_change=None)), 1, NOW
            )
        )
        assert abs(score - math.tanh(5.0 / 5.0)) < 1e-9


class TestDefaultWeightsEarnings:
    def test_base_four_component_no_earnings(self):
        w = _default_weights(has_options=False, has_earnings=False)
        assert w["earnings"] == 0.0
        assert w["rsi"] == 0.0
        assert w["trend"] == 0.0
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9

    def test_earnings_weight_is_tenth_and_sums_to_one(self):
        w = _default_weights(has_options=False, has_earnings=True)
        assert w["earnings"] == WEIGHT_EARNINGS == 0.10
        assert w["rsi"] == 0.0
        assert w["trend"] == 0.0
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9

    def test_options_path_earnings_zero(self):
        w = _default_weights(has_options=True, has_earnings=False)
        assert w["options"] == WEIGHT_OPTIONS == 0.08
        assert w["earnings"] == 0.0
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9

    def test_both_options_and_earnings_sum_to_one(self):
        w = _default_weights(has_options=True, has_earnings=True)
        assert w["earnings"] == 0.10
        assert w["options"] == 0.08
        assert w["rsi"] == 0.0
        assert w["trend"] == 0.0
        numeric = sum(v for k, v in w.items() if k != "source")
        assert abs(numeric - 1.0) < 1e-9


class TestBeatSchedule:
    def test_earnings_fetch_registered_at_6am(self):
        assert "fetch-earnings-calendars" in beat_schedule
        entry = beat_schedule["fetch-earnings-calendars"]
        assert entry["task"] == "worker.tasks.scraping.earnings_data.fetch_all_earnings_calendars"
        schedule = entry["schedule"]
        assert schedule.hour == {6}
        assert schedule.minute == {0}
