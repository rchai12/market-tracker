"""Phase 24b: one strongest signal per 4-hour ET bucket."""

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from worker.utils.daily_aggregation import bucket_signals, compute_net_view, signal_bucket

ET = ZoneInfo("America/New_York")


def _sig(composite: float, direction: str, generated_at: datetime | None, **kwargs):
    return SimpleNamespace(
        composite_score=composite,
        direction=direction,
        generated_at=generated_at,
        **kwargs,
    )


class TestSignalBucket:
    def test_pre_market(self):
        assert signal_bucket(datetime(2026, 9, 14, 8, 0, tzinfo=ET)) == "pre_market"

    def test_morning_open(self):
        assert signal_bucket(datetime(2026, 9, 14, 9, 30, tzinfo=ET)) == "morning"

    def test_morning_before_afternoon(self):
        assert signal_bucket(datetime(2026, 9, 14, 13, 29, tzinfo=ET)) == "morning"

    def test_afternoon_start(self):
        assert signal_bucket(datetime(2026, 9, 14, 13, 30, tzinfo=ET)) == "afternoon"

    def test_after_hours_is_afternoon(self):
        assert signal_bucket(datetime(2026, 9, 14, 16, 30, tzinfo=ET)) == "afternoon"


class TestBucketSignals:
    def test_one_signal_per_bucket_highest_composite_wins(self):
        morning_weak = _sig(0.3, "bullish", datetime(2026, 9, 14, 10, 0, tzinfo=ET))
        morning_strong = _sig(0.9, "bearish", datetime(2026, 9, 14, 11, 0, tzinfo=ET))
        afternoon = _sig(0.4, "bullish", datetime(2026, 9, 14, 14, 0, tzinfo=ET))
        pre = _sig(0.2, "bullish", datetime(2026, 9, 14, 8, 0, tzinfo=ET))
        kept = bucket_signals([morning_weak, morning_strong, afternoon, pre])
        assert len(kept) == 3
        assert morning_strong in kept
        assert morning_weak not in kept
        assert afternoon in kept
        assert pre in kept

    def test_missing_generated_at_defaults_to_afternoon(self):
        a = _sig(0.4, "bullish", None)
        b = _sig(0.8, "bullish", datetime(2026, 9, 14, 15, 0, tzinfo=ET))
        kept = bucket_signals([a, b])
        assert kept == [b]

    def test_raw_count_vs_bucketed_count(self):
        raw = [
            _sig(0.4, "bullish", datetime(2026, 9, 14, 10, 0, tzinfo=ET)),
            _sig(0.5, "bullish", datetime(2026, 9, 14, 11, 0, tzinfo=ET)),
            _sig(0.6, "bullish", datetime(2026, 9, 14, 12, 0, tzinfo=ET)),
            _sig(0.3, "bearish", datetime(2026, 9, 14, 14, 0, tzinfo=ET)),
        ]
        bucketed = bucket_signals(raw)
        view = compute_net_view(bucketed, date(2026, 9, 14))
        assert len(raw) == 4
        assert len(bucketed) == 2
        assert view is not None
        assert view.signal_count == 2
