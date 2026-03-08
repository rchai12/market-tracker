"""Signal schemas for API request/response."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class SignalResponse(BaseModel):
    id: int
    stock_id: int
    ticker: str
    company_name: str
    direction: str
    strength: str
    composite_score: float
    sentiment_score: float | None
    sentiment_volume_score: float | None
    price_score: float | None
    volume_score: float | None
    rsi_score: float | None
    trend_score: float | None
    options_score: float | None = None
    article_count: int
    reasoning: str | None
    ml_score: float | None = None
    ml_direction: str | None = None
    ml_confidence: float | None = None
    generated_at: datetime
    window_start: datetime
    window_end: datetime

    model_config = {"from_attributes": True}


class PaginatedSignals(BaseModel):
    data: list[SignalResponse]
    meta: PaginationMeta


class SignalAccuracyResponse(BaseModel):
    scope: str
    window_days: int
    total_evaluated: int
    correct_count: int
    accuracy_pct: float
    avg_return_correct: float
    avg_return_wrong: float
    bullish_accuracy_pct: float | None = None
    bearish_accuracy_pct: float | None = None


class SignalWeightsResponse(BaseModel):
    sector_name: str | None
    sentiment_momentum: float
    sentiment_volume: float
    price_momentum: float
    volume_anomaly: float
    rsi: float
    trend: float
    options: float
    sample_count: int
    accuracy_pct: float | None
    computed_at: datetime | None
    source: str


class AccuracyTrendPoint(BaseModel):
    period_start: datetime
    period_end: datetime
    total: int
    correct: int
    accuracy_pct: float


class AccuracyBucket(BaseModel):
    label: str
    total: int
    correct: int
    accuracy_pct: float
    avg_return_pct: float


class AccuracyDistribution(BaseModel):
    by_strength: list[AccuracyBucket]
    by_direction: list[AccuracyBucket]


class SignalOutcomeResponse(BaseModel):
    window_days: int
    price_change_pct: float
    is_correct: bool
    evaluated_at: datetime


class LinkedArticle(BaseModel):
    id: int
    title: str
    source: str
    url: str | None
    published_at: datetime | None
    sentiment_label: str | None
    sentiment_score: float | None


class SignalDetailResponse(BaseModel):
    signal: SignalResponse
    outcomes: list[SignalOutcomeResponse]
    linked_articles: list[LinkedArticle]
