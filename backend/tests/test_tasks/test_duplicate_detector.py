"""Tests for the duplicate detector utility."""

import pytest

from worker.utils.duplicate_detector import find_duplicate_group


class TestFindDuplicateGroup:
    def test_high_similarity_matches(self):
        """Similar headlines about the same event should be grouped."""
        recent = [(1, "Apple Reports Record Q4 Earnings Beat Expectations", None)]
        result = find_duplicate_group("Apple Q4 Earnings Reports Beat Expectations", recent)
        assert result == 1  # Uses article_id as new group

    def test_low_similarity_no_match(self):
        """Unrelated articles should not be grouped."""
        recent = [(1, "Tesla Unveils New Model Y Design", None)]
        result = find_duplicate_group("Apple Announces Stock Buyback Program", recent)
        assert result is None

    def test_propagates_existing_group_id(self):
        """Should reuse the matched article's group_id if it has one."""
        recent = [(1, "Fed Raises Interest Rates by 25 Basis Points", 42)]
        result = find_duplicate_group("Federal Reserve Raises Interest Rates 25 Basis Points", recent)
        assert result == 42

    def test_uses_article_id_when_no_group(self):
        """Should use matched article's id if it has no group_id."""
        recent = [(5, "NVIDIA Earnings Beat Wall Street Estimates Q4", None)]
        result = find_duplicate_group("NVIDIA Q4 Earnings Beat Wall Street Estimates", recent)
        assert result == 5

    def test_best_match_wins(self):
        """Should pick the highest-scoring match from multiple candidates."""
        recent = [
            (1, "Completely Unrelated Article About Weather", None),
            (2, "Apple Q4 Earnings Beat Analyst Estimates", None),
            (3, "Apple Reports Q4 Earnings Beat Analyst Estimates", None),
        ]
        result = find_duplicate_group("Apple Q4 Earnings Reports Beat Analyst Estimates", recent)
        assert result is not None
        # Should match one of the Apple earnings articles
        assert result in (2, 3)

    def test_empty_recent_articles(self):
        """Should return None with no candidates."""
        assert find_duplicate_group("Some Article Title", []) is None

    def test_empty_title(self):
        """Should return None with empty title."""
        recent = [(1, "Some Article", None)]
        assert find_duplicate_group("", recent) is None

    def test_identical_titles(self):
        """Identical titles should definitely match."""
        title = "S&P 500 Closes at Record High"
        recent = [(10, title, None)]
        result = find_duplicate_group(title, recent)
        assert result == 10

    def test_custom_threshold(self):
        """Higher threshold should require closer matches."""
        recent = [(1, "Apple Reports Quarterly Earnings", None)]
        # With very high threshold, slightly different titles might not match
        result_strict = find_duplicate_group(
            "Apple Earnings Report Released Today", recent, threshold=98.0
        )
        assert result_strict is None

    def test_none_titles_in_candidates_skipped(self):
        """Articles with None/empty titles in candidates should be skipped."""
        recent = [
            (1, "", None),
            (2, "Apple Earnings Beat Estimates Reports Q4", None),
        ]
        result = find_duplicate_group("Apple Earnings Reports Beat Estimates Q4", recent)
        assert result == 2

    def test_short_titles(self):
        """Short titles should still work."""
        recent = [(1, "Rate Cut", None)]
        result = find_duplicate_group("Rate Cut", recent)
        assert result == 1
