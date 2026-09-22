"""Daily-view accuracy summary: counts, excess-return averages, insufficient_data."""

from worker.utils.daily_accuracy import (
    MIN_VIEWS_FOR_CONFIDENCE,
    AccuracyRow,
    summarize_accuracy,
)


def _row(correct: bool, excess: float, conviction: float = 0.4) -> AccuracyRow:
    return AccuracyRow(conviction=conviction, is_correct=correct, excess_return=excess)


class TestDailyAccuracySummary:
    def test_accuracy_pct_and_excess_averages(self):
        rows = [
            _row(True, 0.0124),
            _row(True, 0.0124),
            _row(False, -0.0083),
        ]
        # plus two unevaluated views
        rows.extend(
            [
                AccuracyRow(conviction=0.5, is_correct=None, excess_return=None),
                AccuracyRow(conviction=0.5, is_correct=None, excess_return=None),
            ]
        )
        summary = summarize_accuracy(rows)
        assert summary["total_views"] == 5
        assert summary["evaluated_views"] == 3
        assert summary["correct"] == 2
        assert abs(summary["accuracy_pct"] - 66.7) < 0.05
        assert summary["avg_excess_return_correct"] == 1.24
        assert summary["avg_excess_return_incorrect"] == -0.83
        assert summary["insufficient_data"] is True

    def test_insufficient_data_below_30(self):
        rows = [_row(True, 0.01) for _ in range(29)]
        summary = summarize_accuracy(rows)
        assert summary["evaluated_views"] == 29
        assert summary["insufficient_data"] is True
        assert summary["min_views_for_confidence"] == MIN_VIEWS_FOR_CONFIDENCE

    def test_insufficient_data_below_confidence_floor(self):
        rows = [_row(True, 0.01) for _ in range(MIN_VIEWS_FOR_CONFIDENCE - 1)]
        assert summarize_accuracy(rows)["insufficient_data"] is True

    def test_sufficient_at_confidence_floor(self):
        rows = [_row(i % 2 == 0, 0.01 if i % 2 == 0 else -0.01) for i in range(MIN_VIEWS_FOR_CONFIDENCE)]
        summary = summarize_accuracy(rows)
        assert summary["insufficient_data"] is False
        assert summary["evaluated_views"] == MIN_VIEWS_FOR_CONFIDENCE
        assert summary["accuracy_pct"] == 50.0

    def test_empty_is_insufficient(self):
        summary = summarize_accuracy([])
        assert summary["evaluated_views"] == 0
        assert summary["accuracy_pct"] == 0.0
        assert summary["insufficient_data"] is True
        assert summary["avg_excess_return_all"] == 0.0
