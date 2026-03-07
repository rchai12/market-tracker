"""Sentiment schemas for API responses."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class SentimentScoreResponse(BaseModel):
    id: int
    article_id: int
    stock_id: int | None
    label: str
    positive_score: float
    negative_score: float
    neutral_score: float
    model_version: str
    processed_at: datetime
    article_title: str | None = None
    article_source: str | None = None
    article_source_url: str | None = None

    model_config = {"from_attributes": True}


class SentimentSummary(BaseModel):
    """Aggregated sentiment for a ticker or sector."""
    ticker: str | None = None
    sector: str | None = None
    total_articles: int
    positive_count: int
    negative_count: int
    neutral_count: int
    avg_positive: float
    avg_negative: float
    avg_neutral: float
    dominant_label: str


class SentimentTimePoint(BaseModel):
    """Single point in a sentiment time series."""
    date: str
    avg_positive: float
    avg_negative: float
    avg_neutral: float
    article_count: int
    dominant_label: str


class PaginatedSentiment(BaseModel):
    data: list[SentimentScoreResponse]
    meta: PaginationMeta
