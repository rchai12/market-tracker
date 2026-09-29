"""Phase 25a: event-category sentiment multipliers."""

from worker.utils.article_quality import event_category_weight

SPEC_CATEGORIES = {
    "earnings": 1.0,
    "analyst": 1.0,
    "insider": 1.0,
    "product": 1.0,
    "m_a": 1.0,
    "dividend": 1.0,
    "legal": 0.80,
    "regulatory": 0.60,
    "macro": 0.50,
    "general": 0.85,
}

LIVE_ALIASES = {
    "analyst_rating": 1.0,
    "insider_trade": 1.0,
    "product_launch": 1.0,
    "merger_acquisition": 1.0,
    "macro_economic": 0.50,
    "general_news": 0.85,
    "material_event": 1.0,
}


class TestEventCategoryWeight:
    def test_all_ten_spec_categories(self):
        for category, expected in SPEC_CATEGORIES.items():
            assert event_category_weight(category) == expected, category

    def test_live_classifier_aliases(self):
        for category, expected in LIVE_ALIASES.items():
            assert event_category_weight(category) == expected, category

    def test_unknown_and_missing_are_full_weight(self):
        assert event_category_weight(None) == 1.0
        assert event_category_weight("") == 1.0
        assert event_category_weight("not_a_category") == 1.0
