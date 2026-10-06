"""Phase 25b: sector sentiment lookup from the pre-computed map."""

from worker.tasks.signals.component_scores import calc_sector_sentiment_score


class TestCalcSectorSentimentScore:
    def test_returns_mapped_value(self):
        mapped = {"Financials": 0.32, "Energy": -0.15}
        assert calc_sector_sentiment_score(mapped, "Financials") == 0.32
        assert calc_sector_sentiment_score(mapped, "Energy") == -0.15

    def test_none_when_gate_inactive(self):
        mapped = {"Financials": None, "Energy": -0.15}
        assert calc_sector_sentiment_score(mapped, "Financials") is None

    def test_none_when_sector_missing(self):
        assert calc_sector_sentiment_score({"Energy": 0.1}, "Technology") is None

    def test_none_when_sector_name_missing(self):
        assert calc_sector_sentiment_score({"Financials": 0.2}, None) is None
        assert calc_sector_sentiment_score({"Financials": 0.2}, "") is None

    def test_zero_is_distinct_from_none(self):
        assert calc_sector_sentiment_score({"Financials": 0.0}, "Financials") == 0.0
