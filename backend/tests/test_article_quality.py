"""Tests for article quality scoring."""

from app.config import DEFAULT_SOURCE_CREDIBILITY, SOURCE_CREDIBILITY
from worker.utils.article_quality import (
    ARTICLE_UI_MIN_TICKER_CONFIDENCE,
    QUALITY_THRESHOLD,
    SIGNAL_EXCLUDED_SOURCES,
    SIGNAL_MIN_TICKER_CONFIDENCE,
    _QUANTITATIVE_RE,
    compute_article_quality,
)

_SEC_MAP = SOURCE_CREDIBILITY
_LONG_TEXT = " ".join(["word"] * 150)
_QUANT_TEXT = "Revenue grew 12.5% to $500 million with EPS of $2."
_LONG_QUANT = _QUANT_TEXT + " " + _LONG_TEXT


class TestComputeArticleQuality:
    def test_high_quality_article_scores_above_085(self):
        score = compute_article_quality(
            source="sec_edgar",
            raw_text=_LONG_QUANT,
            max_ticker_confidence=0.95,
            source_credibility_map=_SEC_MAP,
        )
        assert score > 0.85

    def test_reddit_low_quality_scores_below_threshold(self):
        score = compute_article_quality(
            source="reddit_stocks",
            raw_text="lol this stock is going to the moon",
            max_ticker_confidence=0.0,
            source_credibility_map=_SEC_MAP,
        )
        assert score < QUALITY_THRESHOLD
        assert score < 0.40

    def test_unknown_source_uses_default_credibility(self):
        score = compute_article_quality(
            source="unknown_blog",
            raw_text="short",
            max_ticker_confidence=0.0,
            source_credibility_map=_SEC_MAP,
            default_credibility=DEFAULT_SOURCE_CREDIBILITY,
        )
        # 0.40 * 0.5 + remaining factors 0
        assert score == round(0.40 * DEFAULT_SOURCE_CREDIBILITY, 4)

    def test_raw_text_none_does_not_raise(self):
        score = compute_article_quality(
            source="reuters_rss",
            raw_text=None,
            max_ticker_confidence=0.9,
            source_credibility_map=_SEC_MAP,
        )
        assert isinstance(score, float)

    def test_reuters_scraper_key_uses_high_credibility(self):
        assert SOURCE_CREDIBILITY["reuters"] == 0.9
        assert SOURCE_CREDIBILITY["reuters_rss"] == 0.9

    def test_score_always_bounded(self):
        cases = [
            ("sec_edgar", _LONG_QUANT, 1.0),
            ("sec_edgar", _LONG_QUANT, 99.0),
            ("unknown", None, -5.0),
            ("reddit_wallstreetbets", "", 0.0),
            ("finviz", "x", 0.5),
        ]
        for source, text, conf in cases:
            score = compute_article_quality(
                source=source,
                raw_text=text,
                max_ticker_confidence=conf,
                source_credibility_map=_SEC_MAP,
            )
            assert 0.0 <= score <= 1.0

    def test_score_rounds_to_4_decimal_places(self):
        score = compute_article_quality(
            source="unknown",
            raw_text=None,
            max_ticker_confidence=0.0,
            source_credibility_map={},
            default_credibility=1.0 / 3.0,
        )
        # 0.40 * (1/3) = 0.1333...
        as_str = f"{score:.10f}".rstrip("0")
        decimals = len(as_str.split(".")[1]) if "." in as_str else 0
        assert decimals <= 4
        assert score == round(score, 4)


class TestQuantitativeRegex:
    def test_matches_percentage(self):
        assert _QUANTITATIVE_RE.search("gained 12.5% this quarter")

    def test_matches_dollar_magnitude(self):
        assert _QUANTITATIVE_RE.search("deal worth $500M")

    def test_matches_revenue_of_dollars(self):
        assert _QUANTITATIVE_RE.search("revenue of $2B last year")

    def test_matches_basis_points(self):
        assert _QUANTITATIVE_RE.search("spread widened 50 bps")

    def test_does_not_match_qualitative_text(self):
        assert _QUANTITATIVE_RE.search("the company grew strongly") is None


class TestLengthFactorBoundary:
    def test_length_factor_triggers_at_exactly_150_words(self):
        at_boundary = " ".join(["word"] * 150)
        below = " ".join(["word"] * 149)
        # Isolate length by using unknown source, no quant, no tickers
        empty_map: dict[str, float] = {}
        score_at = compute_article_quality("x", at_boundary, 0.0, empty_map, default_credibility=0.0)
        score_below = compute_article_quality("x", below, 0.0, empty_map, default_credibility=0.0)
        assert score_at == 0.10
        assert score_below == 0.0


class TestGateConstants:
    def test_confidence_floor(self):
        assert SIGNAL_MIN_TICKER_CONFIDENCE == 0.70

    def test_ui_confidence_floor_keeps_company_name_drops_industry(self):
        assert ARTICLE_UI_MIN_TICKER_CONFIDENCE == 0.60
        assert ARTICLE_UI_MIN_TICKER_CONFIDENCE < SIGNAL_MIN_TICKER_CONFIDENCE

    def test_reddit_sources_excluded(self):
        assert "reddit" in SIGNAL_EXCLUDED_SOURCES
        assert "reddit_stocks" in SIGNAL_EXCLUDED_SOURCES
        assert "reddit_wallstreetbets" in SIGNAL_EXCLUDED_SOURCES

    def test_articles_endpoint_filters_ticker_by_ui_floor(self):
        import inspect

        from app.api.articles import list_articles

        src = inspect.getsource(list_articles)
        assert "ARTICLE_UI_MIN_TICKER_CONFIDENCE" in src

    def test_sentiment_articles_endpoint_filters_by_ui_floor(self):
        import inspect

        from app.api.sentiment import get_ticker_sentiment_articles

        src = inspect.getsource(get_ticker_sentiment_articles)
        assert "ARTICLE_UI_MIN_TICKER_CONFIDENCE" in src
        assert "exists" in src.lower()
