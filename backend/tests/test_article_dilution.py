"""Phase 25a: multi-stock article dilution curve."""

from worker.utils.article_quality import (
    DILUTION_EXPONENT,
    DILUTION_FLOOR,
    article_dilution_weight,
)


class TestArticleDilutionWeight:
    def test_one_stock_full_weight(self):
        assert article_dilution_weight(1) == 1.0

    def test_three_stocks_full_weight(self):
        assert article_dilution_weight(3) == 1.0

    def test_five_stocks_diminishes(self):
        expected = 1.0 / (5**DILUTION_EXPONENT)
        assert abs(article_dilution_weight(5) - expected) < 1e-12
        assert 0.5 < article_dilution_weight(5) < 1.0

    def test_ten_stocks_diminishes_further(self):
        expected = 1.0 / (10**DILUTION_EXPONENT)
        assert abs(article_dilution_weight(10) - expected) < 1e-12
        assert article_dilution_weight(10) < article_dilution_weight(5)

    def test_twenty_stocks_continues_curve(self):
        expected = 1.0 / (20**DILUTION_EXPONENT)
        assert abs(article_dilution_weight(20) - expected) < 1e-12
        assert article_dilution_weight(20) < article_dilution_weight(10)

    def test_fifty_stocks_still_above_floor(self):
        expected = 1.0 / (50**DILUTION_EXPONENT)
        assert abs(article_dilution_weight(50) - expected) < 1e-12
        assert article_dilution_weight(50) > DILUTION_FLOOR

    def test_floor_enforced_for_very_wide_articles(self):
        assert article_dilution_weight(200) == DILUTION_FLOOR
        assert article_dilution_weight(10_000) == DILUTION_FLOOR
