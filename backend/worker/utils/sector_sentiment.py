"""Sector-level sentiment from spray-confidence and macro/regulatory articles.

Company-specific articles (confidence >= 0.70) stay in per-stock scoring.
These helpers aggregate the leftover sector-spray and macro articles into one
score per sector. The live generator queries, then calls aggregate_sector_sentiment.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from worker.utils.component_math import SENTIMENT_HALF_LIFE_HOURS

MIN_ARTICLES_FOR_SECTOR = 3
SECTOR_SENTIMENT_WINDOW_HOURS = 24
SECTOR_SPRAY_MIN_CONFIDENCE = 0.30  # below this is noise, not sector-spray
SECTOR_SPRAY_MAX_CONFIDENCE = 0.70  # exclusive; 0.70+ is per-stock scoring

SECTOR_EVENT_CATEGORIES = frozenset({"macro", "macro_economic", "regulatory"})


@dataclass(frozen=True)
class SectorArticlePoint:
    """One article contributing to one sector's mood score."""

    article_id: int
    sector: str
    value: float
    hours_ago: float
    credibility: float
    duplicate_group_id: int | None = None


def article_qualifies_for_sector_sentiment(
    confidence: float | None,
    event_category: str | None,
) -> bool:
    """True when the association is sector-spray or the article is macro/regulatory."""
    if event_category in SECTOR_EVENT_CATEGORIES:
        return True
    if confidence is None:
        return False
    return SECTOR_SPRAY_MIN_CONFIDENCE <= float(confidence) < SECTOR_SPRAY_MAX_CONFIDENCE


def aggregate_sector_sentiment(
    points: list[SectorArticlePoint],
    *,
    min_articles: int = MIN_ARTICLES_FOR_SECTOR,
    half_life_hours: float = SENTIMENT_HALF_LIFE_HOURS,
) -> dict[str, float | None]:
    """Weighted average per sector. None when unique articles < min_articles.

    One article contributes once per sector. Duplicate groups keep the
    highest-credibility copy. Weight = source credibility * recency decay
    (same half-life as sentiment momentum).
    """
    unique = _dedupe_points(points)
    by_sector: dict[str, list[SectorArticlePoint]] = defaultdict(list)
    for point in unique:
        by_sector[point.sector].append(point)

    decay_rate = math.log(2) / half_life_hours
    result: dict[str, float | None] = {}
    for sector, articles in by_sector.items():
        if len(articles) < min_articles:
            result[sector] = None
            continue
        weighted_sum = 0.0
        weight_total = 0.0
        for article in articles:
            weight = article.credibility * math.exp(-decay_rate * article.hours_ago)
            weighted_sum += article.value * weight
            weight_total += weight
        result[sector] = (weighted_sum / weight_total) if weight_total else None
    return result


def _dedupe_points(points: list[SectorArticlePoint]) -> list[SectorArticlePoint]:
    by_article: dict[tuple[int, str], SectorArticlePoint] = {}
    for point in points:
        key = (point.article_id, point.sector)
        prev = by_article.get(key)
        if prev is None or point.credibility > prev.credibility:
            by_article[key] = point

    grouped: dict[tuple[int, str], SectorArticlePoint] = {}
    ungrouped: list[SectorArticlePoint] = []
    for point in by_article.values():
        if point.duplicate_group_id is None:
            ungrouped.append(point)
            continue
        key = (point.duplicate_group_id, point.sector)
        prev = grouped.get(key)
        if prev is None or point.credibility > prev.credibility:
            grouped[key] = point
    return ungrouped + list(grouped.values())
