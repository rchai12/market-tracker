"""Tests for signal intelligence features: accuracy trend/distribution, detail linking."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.schemas.signal import (
    AccuracyBucket,
    AccuracyDistribution,
    AccuracyTrendPoint,
    LinkedArticle,
    SignalAccuracyResponse,
    SignalDetailResponse,
    SignalOutcomeResponse,
    SignalResponse,
)


class TestAccuracyTrendPoint:
    """Test AccuracyTrendPoint schema validation."""

    def test_basic_creation(self):
        point = AccuracyTrendPoint(
            period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2025, 1, 8, tzinfo=timezone.utc),
            total=20,
            correct=12,
            accuracy_pct=60.0,
        )
        assert point.total == 20
        assert point.correct == 12
        assert point.accuracy_pct == 60.0

    def test_zero_total(self):
        point = AccuracyTrendPoint(
            period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2025, 1, 8, tzinfo=timezone.utc),
            total=0,
            correct=0,
            accuracy_pct=0,
        )
        assert point.accuracy_pct == 0


class TestAccuracyDistribution:
    """Test AccuracyDistribution and AccuracyBucket schemas."""

    def test_by_strength(self):
        dist = AccuracyDistribution(
            by_strength=[
                AccuracyBucket(label="strong", total=10, correct=8, accuracy_pct=80.0, avg_return_pct=2.5),
                AccuracyBucket(label="moderate", total=30, correct=18, accuracy_pct=60.0, avg_return_pct=1.2),
                AccuracyBucket(label="weak", total=50, correct=25, accuracy_pct=50.0, avg_return_pct=0.3),
            ],
            by_direction=[],
        )
        assert len(dist.by_strength) == 3
        assert dist.by_strength[0].label == "strong"
        assert dist.by_strength[0].accuracy_pct == 80.0

    def test_by_direction(self):
        dist = AccuracyDistribution(
            by_strength=[],
            by_direction=[
                AccuracyBucket(label="bullish", total=40, correct=24, accuracy_pct=60.0, avg_return_pct=1.5),
                AccuracyBucket(label="bearish", total=40, correct=20, accuracy_pct=50.0, avg_return_pct=-0.5),
            ],
        )
        assert len(dist.by_direction) == 2
        assert dist.by_direction[0].avg_return_pct == 1.5

    def test_empty_buckets(self):
        dist = AccuracyDistribution(by_strength=[], by_direction=[])
        assert len(dist.by_strength) == 0
        assert len(dist.by_direction) == 0


class TestSignalOutcomeResponse:
    """Test SignalOutcomeResponse schema."""

    def test_correct_outcome(self):
        outcome = SignalOutcomeResponse(
            window_days=5,
            price_change_pct=0.035,
            is_correct=True,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert outcome.is_correct is True
        assert outcome.window_days == 5

    def test_incorrect_outcome(self):
        outcome = SignalOutcomeResponse(
            window_days=1,
            price_change_pct=-0.02,
            is_correct=False,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert outcome.is_correct is False
        assert outcome.price_change_pct == -0.02


class TestLinkedArticle:
    """Test LinkedArticle schema."""

    def test_full_article(self):
        article = LinkedArticle(
            id=1,
            title="Tesla Q4 earnings beat expectations",
            source="yahoo_finance",
            url="https://example.com/article/1",
            published_at="2025-01-15T10:00:00Z",
            sentiment_label="positive",
            sentiment_score=0.85,
        )
        assert article.source == "yahoo_finance"
        assert article.sentiment_label == "positive"

    def test_minimal_article(self):
        article = LinkedArticle(
            id=2,
            title="Market update",
            source="reuters_rss",
            url=None,
            published_at=None,
            sentiment_label=None,
            sentiment_score=None,
        )
        assert article.url is None
        assert article.sentiment_label is None


class TestSignalDetailResponse:
    """Test SignalDetailResponse schema."""

    def _make_signal_response(self) -> SignalResponse:
        return SignalResponse(
            id=1,
            stock_id=1,
            ticker="AAPL",
            company_name="Apple Inc",
            direction="bullish",
            strength="strong",
            composite_score=0.75,
            sentiment_score=0.6,
            sentiment_volume_score=0.3,
            price_score=0.4,
            volume_score=0.2,
            rsi_score=0.1,
            trend_score=0.15,
            article_count=5,
            reasoning="Strong bullish signal",
            generated_at=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=1),
            window_end=datetime.now(timezone.utc),
        )

    def test_with_outcomes_and_articles(self):
        detail = SignalDetailResponse(
            signal=self._make_signal_response(),
            outcomes=[
                SignalOutcomeResponse(
                    window_days=1,
                    price_change_pct=0.01,
                    is_correct=True,
                    evaluated_at=datetime.now(timezone.utc),
                ),
                SignalOutcomeResponse(
                    window_days=5,
                    price_change_pct=0.03,
                    is_correct=True,
                    evaluated_at=datetime.now(timezone.utc),
                ),
            ],
            linked_articles=[
                LinkedArticle(
                    id=1,
                    title="Apple surges",
                    source="yahoo_finance",
                    url="https://example.com/1",
                    published_at="2025-01-15T10:00:00Z",
                    sentiment_label="positive",
                    sentiment_score=0.9,
                ),
            ],
        )
        assert len(detail.outcomes) == 2
        assert len(detail.linked_articles) == 1
        assert detail.signal.sentiment_volume_score == 0.3

    def test_empty_outcomes_and_articles(self):
        detail = SignalDetailResponse(
            signal=self._make_signal_response(),
            outcomes=[],
            linked_articles=[],
        )
        assert len(detail.outcomes) == 0
        assert len(detail.linked_articles) == 0


class TestSignalResponseWithSentimentVolume:
    """Test that SignalResponse includes the new sentiment_volume_score field."""

    def test_with_sentiment_volume(self):
        resp = SignalResponse(
            id=1,
            stock_id=1,
            ticker="MSFT",
            company_name="Microsoft",
            direction="bullish",
            strength="moderate",
            composite_score=0.45,
            sentiment_score=0.3,
            sentiment_volume_score=0.25,
            price_score=0.2,
            volume_score=0.1,
            rsi_score=0.05,
            trend_score=0.08,
            article_count=3,
            reasoning="Test",
            generated_at=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=1),
            window_end=datetime.now(timezone.utc),
        )
        assert resp.sentiment_volume_score == 0.25

    def test_without_sentiment_volume(self):
        resp = SignalResponse(
            id=2,
            stock_id=1,
            ticker="MSFT",
            company_name="Microsoft",
            direction="neutral",
            strength="weak",
            composite_score=0.05,
            sentiment_score=None,
            sentiment_volume_score=None,
            price_score=None,
            volume_score=None,
            rsi_score=None,
            trend_score=None,
            article_count=0,
            reasoning=None,
            generated_at=datetime.now(timezone.utc),
            window_start=datetime.now(timezone.utc) - timedelta(hours=1),
            window_end=datetime.now(timezone.utc),
        )
        assert resp.sentiment_volume_score is None


class TestComputeAccuracyDirect:
    """Test the real _compute_accuracy helper from the API module."""

    def test_accuracy_computation(self):
        from app.api.signal_accuracy import _compute_accuracy

        Row = type("Row", (), {})
        rows = []
        for direction, is_correct, pct in [
            ("bullish", True, 0.05),
            ("bullish", True, 0.03),
            ("bullish", False, -0.02),
            ("bearish", True, -0.04),
            ("bearish", False, 0.01),
        ]:
            r = Row()
            r.direction = direction
            r.is_correct = is_correct
            r.price_change_pct = pct
            rows.append(r)

        result = _compute_accuracy(rows, "global", 5)

        assert result.total_evaluated == 5
        assert result.correct_count == 3
        assert result.accuracy_pct == 60.0
        assert result.bullish_accuracy_pct is not None
        # 2 out of 3 bullish correct
        assert abs(result.bullish_accuracy_pct - 66.7) < 0.1
        # 1 out of 2 bearish correct
        assert result.bearish_accuracy_pct == 50.0

    def test_accuracy_single_direction(self):
        from app.api.signal_accuracy import _compute_accuracy

        Row = type("Row", (), {})
        rows = []
        for is_correct, pct in [(True, 0.02), (True, 0.03), (False, -0.01)]:
            r = Row()
            r.direction = "bullish"
            r.is_correct = is_correct
            r.price_change_pct = pct
            rows.append(r)

        result = _compute_accuracy(rows, "test", 3)

        assert result.bullish_accuracy_pct is not None
        assert result.bearish_accuracy_pct is None
        assert abs(result.accuracy_pct - 66.7) < 0.1

    def test_all_correct(self):
        from app.api.signal_accuracy import _compute_accuracy

        Row = type("Row", (), {})
        rows = []
        for direction, pct in [("bullish", 0.05), ("bearish", -0.03)]:
            r = Row()
            r.direction = direction
            r.is_correct = True
            r.price_change_pct = pct
            rows.append(r)

        result = _compute_accuracy(rows, "perfect", 1)
        assert result.accuracy_pct == 100.0
        assert result.correct_count == 2

    def test_no_correct(self):
        from app.api.signal_accuracy import _compute_accuracy

        Row = type("Row", (), {})
        rows = []
        for direction, pct in [("bullish", -0.02), ("bearish", 0.01)]:
            r = Row()
            r.direction = direction
            r.is_correct = False
            r.price_change_pct = pct
            rows.append(r)

        result = _compute_accuracy(rows, "bad", 5)
        assert result.accuracy_pct == 0.0
        assert result.avg_return_correct == 0


class TestAccuracyBucketBuildLogic:
    """Test the bucket building logic from accuracy/distribution endpoint."""

    def test_bucket_grouping(self):
        """Verify the grouping logic that the endpoint uses."""
        Row = type("Row", (), {})
        rows = []
        for strength, direction, is_correct, pct in [
            ("strong", "bullish", True, 0.05),
            ("strong", "bullish", True, 0.03),
            ("moderate", "bullish", False, -0.02),
            ("moderate", "bearish", True, -0.04),
            ("weak", "bearish", False, 0.01),
        ]:
            r = Row()
            r.strength = strength
            r.direction = direction
            r.is_correct = is_correct
            r.price_change_pct = pct
            rows.append(r)

        # Simulate the grouping logic from the endpoint
        def _build_buckets(rows_list, key_fn):
            groups = {}
            for r in rows_list:
                key = key_fn(r)
                groups.setdefault(key, []).append(r)

            buckets = []
            for label, group in sorted(groups.items()):
                total = len(group)
                correct = sum(1 for r in group if r.is_correct)
                returns = [float(r.price_change_pct) for r in group]
                buckets.append(
                    AccuracyBucket(
                        label=label,
                        total=total,
                        correct=correct,
                        accuracy_pct=round(correct / total * 100, 1) if total else 0,
                        avg_return_pct=round(sum(returns) / len(returns) * 100, 3) if returns else 0,
                    )
                )
            return buckets

        by_strength = _build_buckets(rows, lambda r: r.strength)
        assert len(by_strength) == 3
        # Strong: 2 correct out of 2
        strong = next(b for b in by_strength if b.label == "strong")
        assert strong.total == 2
        assert strong.correct == 2
        assert strong.accuracy_pct == 100.0

        by_direction = _build_buckets(rows, lambda r: r.direction)
        assert len(by_direction) == 2
        bullish = next(b for b in by_direction if b.label == "bullish")
        assert bullish.total == 3
        assert bullish.correct == 2


class TestTrendBucketing:
    """Test the time bucketing logic for accuracy trends."""

    def test_weekly_bucketing(self):
        """Verify weekly bucketing groups outcomes correctly."""
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)
        cutoff = now - timedelta(days=30)
        bucket_days = 7

        # Create mock evaluated_at dates
        dates = [
            cutoff + timedelta(days=2),   # bucket 0
            cutoff + timedelta(days=5),   # bucket 0
            cutoff + timedelta(days=8),   # bucket 1
            cutoff + timedelta(days=15),  # bucket 2
            cutoff + timedelta(days=22),  # bucket 3
        ]

        buckets = {}
        for d in dates:
            days_since = (d - cutoff).days
            bucket_index = days_since // bucket_days
            bucket_start = cutoff + timedelta(days=bucket_index * bucket_days)
            key = bucket_start
            if key not in buckets:
                buckets[key] = {"count": 0}
            buckets[key]["count"] += 1

        assert len(buckets) == 4
        # First bucket should have 2 entries
        first_key = min(buckets.keys())
        assert buckets[first_key]["count"] == 2

    def test_monthly_bucketing(self):
        """Verify monthly bucketing uses 30-day intervals."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)
        cutoff = now - timedelta(days=90)
        bucket_days = 30

        dates = [
            cutoff + timedelta(days=5),   # bucket 0
            cutoff + timedelta(days=25),  # bucket 0
            cutoff + timedelta(days=35),  # bucket 1
            cutoff + timedelta(days=65),  # bucket 2
        ]

        buckets = {}
        for d in dates:
            days_since = (d - cutoff).days
            bucket_index = days_since // bucket_days
            key = bucket_index
            if key not in buckets:
                buckets[key] = 0
            buckets[key] += 1

        assert len(buckets) == 3
        assert buckets[0] == 2  # First 30 days: 2 entries
