"""FinBERT sentiment analyzer — singleton model with batch inference."""

import logging
from typing import ClassVar

from app.config import settings

logger = logging.getLogger(__name__)

LABELS = ["positive", "negative", "neutral"]


class FinBERTAnalyzer:
    """Singleton FinBERT model for financial sentiment analysis.

    Loads the model once and reuses across Celery task invocations.
    Uses torch.no_grad() and CPU inference for memory efficiency on ARM VMs.
    """

    _instance: ClassVar["FinBERTAnalyzer | None"] = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_loaded(self):
        """Lazy-load model on first use."""
        if self._model is not None:
            return

        import torch  # noqa: F811
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        model_path = settings.finbert_model_path
        logger.info(f"Loading FinBERT model from {model_path}...")

        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self._model.eval()

        # Force CPU (ARM VMs don't have CUDA)
        self._model = self._model.to("cpu")
        logger.info("FinBERT model loaded successfully")

    def analyze_batch(self, texts: list[str]) -> list[dict]:
        """Run sentiment analysis on a batch of texts.

        Returns list of dicts with keys: label, positive, negative, neutral
        """
        if not texts:
            return []

        self._ensure_loaded()

        results = []
        batch_size = settings.finbert_batch_size
        max_length = settings.finbert_max_length

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = self._infer_batch(batch, max_length)
            results.extend(batch_results)

        return results

    def _infer_batch(self, texts: list[str], max_length: int) -> list[dict]:
        """Run inference on a single batch."""
        import torch

        inputs = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)

        results = []
        for probs in probabilities:
            pos, neg, neu = probs[0].item(), probs[1].item(), probs[2].item()
            label = LABELS[probs.argmax().item()]
            results.append({
                "label": label,
                "positive": round(pos, 5),
                "negative": round(neg, 5),
                "neutral": round(neu, 5),
            })

        return results

    def analyze_text(self, text: str) -> dict:
        """Analyze a single text. Convenience wrapper around analyze_batch."""
        results = self.analyze_batch([text])
        return results[0] if results else {"label": "neutral", "positive": 0.0, "negative": 0.0, "neutral": 1.0}

    def chunk_and_analyze(self, text: str) -> dict:
        """For long texts, chunk into max_length segments and average the scores.

        Splits on sentence boundaries when possible.
        """
        if not text:
            return {"label": "neutral", "positive": 0.0, "negative": 0.0, "neutral": 1.0}

        max_length = settings.finbert_max_length
        # Rough char estimate: ~4 chars per token
        max_chars = max_length * 4

        if len(text) <= max_chars:
            return self.analyze_text(text)

        # Split into chunks at sentence boundaries
        chunks = self._split_into_chunks(text, max_chars)
        if not chunks:
            return self.analyze_text(text[:max_chars])

        results = self.analyze_batch(chunks)

        # Average scores across chunks
        avg_pos = sum(r["positive"] for r in results) / len(results)
        avg_neg = sum(r["negative"] for r in results) / len(results)
        avg_neu = sum(r["neutral"] for r in results) / len(results)

        scores = {"positive": avg_pos, "negative": avg_neg, "neutral": avg_neu}
        label = max(scores, key=scores.get)

        return {
            "label": label,
            "positive": round(avg_pos, 5),
            "negative": round(avg_neg, 5),
            "neutral": round(avg_neu, 5),
        }

    @staticmethod
    def _split_into_chunks(text: str, max_chars: int) -> list[str]:
        """Split text into chunks at sentence boundaries."""
        sentences = text.replace("\n", " ").split(". ")
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = current_chunk + ". " + sentence if current_chunk else sentence

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
