"""Tests for text cleaning utilities."""

from worker.utils.text_cleaner import clean_article_text, normalize_whitespace, strip_html, truncate


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_handles_plain_text(self):
        assert strip_html("No HTML here") == "No HTML here"

    def test_handles_empty_string(self):
        assert strip_html("") == ""


class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert normalize_whitespace("hello   world") == "hello world"

    def test_handles_newlines_and_tabs(self):
        assert normalize_whitespace("hello\n\n\tworld") == "hello world"

    def test_strips_leading_trailing(self):
        assert normalize_whitespace("  hello  ") == "hello"


class TestTruncate:
    def test_short_text_unchanged(self):
        assert truncate("short", 100) == "short"

    def test_long_text_truncated(self):
        result = truncate("a" * 200, 100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")


class TestCleanArticleText:
    def test_full_pipeline(self):
        html = "<p>Hello   <b>world</b></p>"
        result = clean_article_text(html)
        assert result == "Hello world"

    def test_none_input(self):
        assert clean_article_text(None) is None

    def test_empty_string(self):
        assert clean_article_text("") is None
