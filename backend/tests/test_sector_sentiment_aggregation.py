"""Phase 25b: sector-sentiment aggregation math."""

import math

from worker.utils.component_math import SENTIMENT_HALF_LIFE_HOURS
from worker.utils.sector_sentiment import (
    MIN_ARTICLES_FOR_SECTOR,
    SectorArticlePoint,
    aggregate_sector_sentiment,
)


def _point(
    article_id: int,
    sector: str = "Financials",
    value: float = 0.8,
    hours_ago: float = 0.0,
    credibility: float = 1.0,
    duplicate_group_id: int | None = None,
) -> SectorArticlePoint:
    return SectorArticlePoint(
        article_id=article_id,
        sector=sector,
        value=value,
        hours_ago=hours_ago,
        credibility=credibility,
        duplicate_group_id=duplicate_group_id,
    )


class TestAggregateSectorSentiment:
    def test_none_when_fewer_than_min_articles(self):
        points = [_point(i) for i in range(MIN_ARTICLES_FOR_SECTOR - 1)]
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is None

    def test_score_when_min_articles_met(self):
        points = [_point(i, value=0.5) for i in range(MIN_ARTICLES_FOR_SECTOR)]
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is not None
        assert abs(result["Financials"] - 0.5) < 1e-12

    def test_same_article_two_stocks_counts_once(self):
        points = [_point(1, value=0.9), _point(1, value=0.1), _point(2, value=0.4), _point(3, value=0.4)]
        # article 1 appears twice; unique count is 3 so gate opens
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is not None

        two_unique = [_point(1, value=0.9), _point(1, value=0.1), _point(2, value=0.4)]
        sparse = aggregate_sector_sentiment(two_unique)
        assert sparse["Financials"] is None

    def test_recency_decay_weights_recent_articles_more(self):
        points = [
            _point(1, value=1.0, hours_ago=0.0),
            _point(2, value=-1.0, hours_ago=SENTIMENT_HALF_LIFE_HOURS),
            _point(3, value=-1.0, hours_ago=SENTIMENT_HALF_LIFE_HOURS),
        ]
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is not None
        # Recent +1.0 at weight 1 vs two aged -1.0 at weight 0.5 each → 0
        assert abs(result["Financials"]) < 1e-12

    def test_credibility_weights_the_average(self):
        points = [
            _point(1, value=1.0, credibility=1.0),
            _point(2, value=-1.0, credibility=0.5),
            _point(3, value=-1.0, credibility=0.5),
        ]
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is not None
        assert abs(result["Financials"]) < 1e-12

    def test_duplicate_group_counts_as_one(self):
        points = [
            _point(1, value=0.8, credibility=0.9, duplicate_group_id=10),
            _point(2, value=-0.8, credibility=0.4, duplicate_group_id=10),
            _point(3, value=0.8),
            _point(4, value=0.8),
        ]
        result = aggregate_sector_sentiment(points)
        # unique: group 10 (kept 0.8) + 3 + 4 = 3 articles, all +0.8
        assert result["Financials"] is not None
        assert abs(result["Financials"] - 0.8) < 1e-12

    def test_sectors_are_independent(self):
        points = [
            _point(1, sector="Financials", value=0.6),
            _point(2, sector="Financials", value=0.6),
            _point(3, sector="Energy", value=-0.4),
        ]
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is None  # only 2
        assert result["Energy"] is None  # only 1

    def test_half_life_matches_momentum_kernel(self):
        decay = math.exp(-math.log(2))
        points = [
            _point(1, value=1.0, hours_ago=0.0, credibility=1.0),
            _point(2, value=-1.0, hours_ago=SENTIMENT_HALF_LIFE_HOURS, credibility=1.0),
            _point(3, value=0.0, hours_ago=0.0, credibility=0.0),  # zero weight, still counts
        ]
        result = aggregate_sector_sentiment(points)
        assert result["Financials"] is not None
        expected = (1.0 * 1.0 + (-1.0) * decay) / (1.0 + decay)
        assert abs(result["Financials"] - expected) < 1e-12
