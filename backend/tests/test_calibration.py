"""Conviction calibration buckets and thin-bucket hiding."""

from worker.utils.daily_accuracy import (
    AccuracyRow,
    aggregate_calibration,
    calibration_is_thin,
    conviction_bucket,
)


class TestConvictionBuckets:
    def test_boundaries(self):
        assert conviction_bucket(0.19) is None
        assert conviction_bucket(0.20) == "Low"
        assert conviction_bucket(0.349) == "Low"
        assert conviction_bucket(0.35) == "Medium"
        assert conviction_bucket(0.499) == "Medium"
        assert conviction_bucket(0.50) == "High"
        assert conviction_bucket(0.649) == "High"
        assert conviction_bucket(0.65) == "Very High"
        assert conviction_bucket(1.0) == "Very High"

    def test_accuracy_per_bucket(self):
        rows = [
            *[AccuracyRow(0.25, True, 0.01) for _ in range(8)],
            *[AccuracyRow(0.25, False, -0.01) for _ in range(2)],
            *[AccuracyRow(0.40, True, 0.02) for _ in range(6)],
            *[AccuracyRow(0.40, False, -0.01) for _ in range(4)],
            *[AccuracyRow(0.55, True, 0.03) for _ in range(7)],
            *[AccuracyRow(0.55, False, -0.01) for _ in range(3)],
            *[AccuracyRow(0.80, True, 0.04) for _ in range(8)],
            *[AccuracyRow(0.80, False, -0.01) for _ in range(2)],
        ]
        buckets = {b["label"]: b for b in aggregate_calibration(rows)}
        assert buckets["Low"]["count"] == 10
        assert buckets["Low"]["accuracy_pct"] == 80.0
        assert buckets["Medium"]["accuracy_pct"] == 60.0
        assert buckets["High"]["accuracy_pct"] == 70.0
        assert buckets["Very High"]["accuracy_pct"] == 80.0
        assert buckets["Low"]["min_conviction"] == 0.20
        assert buckets["Very High"]["max_conviction"] == 1.0

    def test_always_four_buckets_even_when_empty(self):
        buckets = aggregate_calibration([])
        assert [b["label"] for b in buckets] == ["Low", "Medium", "High", "Very High"]
        assert all(b["count"] == 0 for b in buckets)

    def test_hidden_when_any_bucket_thin(self):
        rows = [
            *[AccuracyRow(0.25, True, 0.01) for _ in range(10)],
            *[AccuracyRow(0.40, True, 0.01) for _ in range(10)],
            *[AccuracyRow(0.55, True, 0.01) for _ in range(10)],
            *[AccuracyRow(0.80, True, 0.01) for _ in range(9)],
        ]
        buckets = aggregate_calibration(rows)
        assert calibration_is_thin(buckets) is True
        rows.append(AccuracyRow(0.80, True, 0.01))
        assert calibration_is_thin(aggregate_calibration(rows)) is False
