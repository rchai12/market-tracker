"""Phase 24b: exponential recency weights toward session close."""

import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

from worker.utils.daily_aggregation import RECENCY_LAMBDA, recency_weight

ET = ZoneInfo("America/New_York")
TRADING = date(2026, 9, 14)


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 14, hour, minute, tzinfo=ET)


class TestRecencyWeight:
    def test_close_of_day_is_one(self):
        assert recency_weight(_at(16, 0), TRADING) == 1.0

    def test_after_close_does_not_boost_above_one(self):
        assert recency_weight(_at(16, 30), TRADING) == 1.0

    def test_table_values(self):
        cases = [
            (_at(15, 30), 0.5, 0.93),
            (_at(13, 30), 2.5, 0.69),
            (_at(11, 30), 4.5, 0.51),
            (_at(9, 30), 6.5, 0.38),
            (_at(7, 0), 9.0, 0.26),
        ]
        for ts, hours, rounded in cases:
            expected = math.exp(-RECENCY_LAMBDA * hours)
            assert abs(recency_weight(ts, TRADING) - expected) < 1e-12
            assert abs(recency_weight(ts, TRADING) - rounded) < 0.01

    def test_pre_market_decays_more_than_open(self):
        pre = recency_weight(_at(7, 0), TRADING)
        open_ = recency_weight(_at(9, 30), TRADING)
        close = recency_weight(_at(16, 0), TRADING)
        assert pre < open_ < close

    def test_after_hours_uses_hours_before_next_close(self):
        generated = datetime(2026, 9, 14, 20, 0, tzinfo=ET)
        next_session = date(2026, 9, 15)
        hours = 20.0  # 20:00 Monday → 16:00 Tuesday
        assert abs(recency_weight(generated, next_session) - math.exp(-RECENCY_LAMBDA * hours)) < 1e-12

    def test_naive_datetime_treated_as_et(self):
        naive = datetime(2026, 9, 14, 16, 0)
        aware = _at(16, 0)
        assert recency_weight(naive, TRADING) == recency_weight(aware, TRADING)
