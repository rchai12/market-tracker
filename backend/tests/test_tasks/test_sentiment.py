"""Tests for sentiment analysis logic (no model loading required)."""

from unittest.mock import MagicMock, patch

from worker.tasks.sentiment.finbert_analyzer import FinBERTAnalyzer


class TestFinBERTChunking:
    def test_split_into_chunks_short_text(self):
        text = "This is a short text."
        chunks = FinBERTAnalyzer._split_into_chunks(text, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0] == "This is a short text."

    def test_split_into_chunks_long_text(self):
        sentences = ["Sentence number {}.".format(i) for i in range(20)]
        text = ". ".join(sentences)
        chunks = FinBERTAnalyzer._split_into_chunks(text, max_chars=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 120  # allow some overflow at sentence boundaries

    def test_split_into_chunks_empty_text(self):
        chunks = FinBERTAnalyzer._split_into_chunks("", max_chars=100)
        assert chunks == []

    def test_split_preserves_all_content(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = FinBERTAnalyzer._split_into_chunks(text, max_chars=40)
        recombined = ". ".join(chunks)
        # All sentences should be present
        assert "First" in recombined
        assert "Fourth" in recombined


class TestFinBERTAnalyzerMocked:
    """Test analyzer methods with mocked model."""

    def test_analyze_batch_empty(self):
        analyzer = FinBERTAnalyzer()
        # analyze_batch with empty input should return empty without loading model
        result = analyzer.analyze_batch([])
        assert result == []

    def test_chunk_and_analyze_empty(self):
        analyzer = FinBERTAnalyzer()
        result = analyzer.chunk_and_analyze("")
        assert result["label"] == "neutral"
        assert result["neutral"] == 1.0

    @patch.object(FinBERTAnalyzer, "_ensure_loaded")
    @patch.object(FinBERTAnalyzer, "_infer_batch")
    def test_analyze_batch_calls_infer(self, mock_infer, mock_load):
        mock_infer.return_value = [
            {"label": "positive", "positive": 0.85, "negative": 0.05, "neutral": 0.10}
        ]

        analyzer = FinBERTAnalyzer()
        analyzer._model = MagicMock()  # pretend model is loaded
        result = analyzer.analyze_batch(["Stock rallied today"])

        assert len(result) == 1
        assert result[0]["label"] == "positive"
        assert result[0]["positive"] == 0.85

    @patch.object(FinBERTAnalyzer, "analyze_batch")
    def test_chunk_and_analyze_short_text(self, mock_batch):
        mock_batch.return_value = [
            {"label": "negative", "positive": 0.1, "negative": 0.8, "neutral": 0.1}
        ]

        analyzer = FinBERTAnalyzer()
        result = analyzer.chunk_and_analyze("Market crashed today")

        assert result["label"] == "negative"
        mock_batch.assert_called_once()

    @patch.object(FinBERTAnalyzer, "analyze_batch")
    def test_chunk_and_analyze_long_text_averages(self, mock_batch):
        # Simulate two chunks with different sentiments
        mock_batch.return_value = [
            {"label": "positive", "positive": 0.8, "negative": 0.1, "neutral": 0.1},
            {"label": "negative", "positive": 0.1, "negative": 0.8, "neutral": 0.1},
        ]

        analyzer = FinBERTAnalyzer()
        # Create text long enough to be chunked (> 512 * 4 = 2048 chars)
        long_text = "Market news. " * 500
        result = analyzer.chunk_and_analyze(long_text)

        # Average of 0.8 and 0.1 = 0.45
        assert 0.4 <= result["positive"] <= 0.5
        assert 0.4 <= result["negative"] <= 0.5


class TestSentimentTaskHelpers:
    def test_get_analysis_text_prefers_raw_text(self):
        from worker.tasks.sentiment.sentiment_task import _get_analysis_text

        article = MagicMock()
        article.raw_text = "This is the full article body text."
        article.summary = "Short summary"
        article.title = "Title"

        result = _get_analysis_text(article)
        assert result == "This is the full article body text."

    def test_get_analysis_text_falls_back_to_summary(self):
        from worker.tasks.sentiment.sentiment_task import _get_analysis_text

        article = MagicMock()
        article.raw_text = ""
        article.summary = "This is a decent summary text."
        article.title = "Title"

        result = _get_analysis_text(article)
        assert result == "This is a decent summary text."

    def test_get_analysis_text_falls_back_to_title(self):
        from worker.tasks.sentiment.sentiment_task import _get_analysis_text

        article = MagicMock()
        article.raw_text = None
        article.summary = None
        article.title = "Stock market crashes on inflation fears"

        result = _get_analysis_text(article)
        assert result == "Stock market crashes on inflation fears"
