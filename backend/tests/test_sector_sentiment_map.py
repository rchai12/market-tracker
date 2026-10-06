"""Phase 25b: sector-sentiment pre-pass filters and grouping."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from worker.tasks.signals.signal_generator import _compute_sector_sentiment_map
from worker.utils.sector_sentiment import (
    SECTOR_SPRAY_MAX_CONFIDENCE,
    SECTOR_SPRAY_MIN_CONFIDENCE,
    article_qualifies_for_sector_sentiment,
)

NOW = datetime(2026, 9, 29, 16, 30, tzinfo=UTC)


def _sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()


def _session(rows: list) -> tuple[AsyncMock, list]:
    captured: list = []
    session = AsyncMock()

    async def execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.all.return_value = rows
        return result

    session.execute = execute
    return session, captured


def _row(
    *,
    article_id: int,
    sector: str = "Financials",
    pos: float = 0.8,
    neg: float = 0.1,
    confidence: float = 0.45,
    event_category: str = "general_news",
    source: str = "reuters",
    dup=None,
):
    return SimpleNamespace(
        id=article_id,
        source=source,
        event_category=event_category,
        published_at=NOW,
        duplicate_group_id=dup,
        positive_score=pos,
        negative_score=neg,
        processed_at=NOW,
        confidence=confidence,
        name=sector,
    )


class TestArticleQualifies:
    def test_sector_spray_included(self):
        assert article_qualifies_for_sector_sentiment(0.45, "earnings") is True
        assert article_qualifies_for_sector_sentiment(0.30, "general_news") is True
        assert article_qualifies_for_sector_sentiment(0.69, "product_launch") is True

    def test_high_confidence_company_news_excluded(self):
        assert article_qualifies_for_sector_sentiment(0.70, "earnings") is False
        assert article_qualifies_for_sector_sentiment(0.95, "earnings") is False

    def test_below_spray_floor_excluded(self):
        assert article_qualifies_for_sector_sentiment(0.29, "earnings") is False

    def test_macro_included_regardless_of_confidence(self):
        assert article_qualifies_for_sector_sentiment(0.95, "macro") is True
        assert article_qualifies_for_sector_sentiment(0.95, "macro_economic") is True
        assert article_qualifies_for_sector_sentiment(0.10, "regulatory") is True


class TestSectorSentimentMap:
    def test_query_filters_spray_range_and_macro(self):
        session, captured = _session([])
        asyncio.run(_compute_sector_sentiment_map(session, ["Financials"], NOW))
        sql = _sql(captured[0])
        assert "0.3" in sql or str(SECTOR_SPRAY_MIN_CONFIDENCE) in sql
        assert "0.7" in sql or str(SECTOR_SPRAY_MAX_CONFIDENCE) in sql
        assert "macro_economic" in sql
        assert "regulatory" in sql
        assert "quality_score" in sql
        assert "canonical_article_id" in sql

    def test_groups_articles_by_sector(self):
        rows = [
            _row(article_id=1, sector="Financials"),
            _row(article_id=1, sector="Financials", confidence=0.40),  # same article, second stock
            _row(article_id=2, sector="Financials"),
            _row(article_id=3, sector="Financials"),
            _row(article_id=4, sector="Energy"),
        ]
        session, _ = _session(rows)
        result = asyncio.run(_compute_sector_sentiment_map(session, ["Financials", "Energy"], NOW))
        assert result["Financials"] is not None
        assert result["Energy"] is None  # only 1 unique article

    def test_macro_high_confidence_is_included(self):
        rows = [
            _row(article_id=1, confidence=0.95, event_category="macro_economic"),
            _row(article_id=2, confidence=0.90, event_category="regulatory"),
            _row(article_id=3, confidence=0.85, event_category="macro"),
        ]
        session, _ = _session(rows)
        result = asyncio.run(_compute_sector_sentiment_map(session, ["Financials"], NOW))
        assert result["Financials"] is not None

    def test_high_confidence_earnings_not_included(self):
        rows = [
            _row(article_id=1, confidence=0.95, event_category="earnings"),
            _row(article_id=2, confidence=0.90, event_category="earnings"),
            _row(article_id=3, confidence=0.85, event_category="earnings"),
        ]
        session, _ = _session(rows)
        result = asyncio.run(_compute_sector_sentiment_map(session, ["Financials"], NOW))
        assert result["Financials"] is None

    def test_missing_sector_stays_none(self):
        session, _ = _session([])
        result = asyncio.run(_compute_sector_sentiment_map(session, ["Technology"], NOW))
        assert result["Technology"] is None
