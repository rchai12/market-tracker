"""Weekly accuracy trend bucketing."""

from datetime import date

from worker.utils.daily_accuracy import AccuracyRow, aggregate_weekly_trend, iso_week_start


class TestAccuracyTrend:
    def test_week_start_is_monday(self):
        # 2026-08-05 is a Wednesday
        assert iso_week_start(date(2026, 8, 5)) == date(2026, 8, 3)
        assert iso_week_start(date(2026, 8, 3)) == date(2026, 8, 3)
        assert iso_week_start(date(2026, 8, 9)) == date(2026, 8, 3)  # Sunday

    def test_same_iso_week_collapses(self):
        rows = [
            AccuracyRow(0.4, True, 0.01, trading_date=date(2026, 8, 3)),
            AccuracyRow(0.5, False, -0.01, trading_date=date(2026, 8, 5)),
            AccuracyRow(0.6, True, 0.02, trading_date=date(2026, 8, 7)),
            AccuracyRow(0.4, True, 0.01, trading_date=date(2026, 8, 10)),
        ]
        buckets = aggregate_weekly_trend(rows)
        assert [b["week_start"] for b in buckets] == [date(2026, 8, 3), date(2026, 8, 10)]
        first = buckets[0]
        assert first["view_count"] == 3
        assert abs(first["accuracy_pct"] - 66.7) < 0.05
        assert first["avg_conviction"] == 0.5
        assert buckets[1]["view_count"] == 1
        assert buckets[1]["accuracy_pct"] == 100.0

    def test_skips_unevaluated(self):
        rows = [
            AccuracyRow(0.4, None, None, trading_date=date(2026, 8, 3)),
            AccuracyRow(0.4, True, 0.01, trading_date=date(2026, 8, 4)),
        ]
        buckets = aggregate_weekly_trend(rows)
        assert len(buckets) == 1
        assert buckets[0]["view_count"] == 1
