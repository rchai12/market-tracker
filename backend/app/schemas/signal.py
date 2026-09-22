"""Signal schemas for API request/response."""

from datetime import date, datetime

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
    has_ml: bool = False
    market_regime: str | None = None
    earnings_score: float | None = None
    analyst_score: float | None = None
    insider_score: float | None = None
    retail_sentiment_score: float | None = None
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
    earnings: float
    analyst: float
    insider: float = 0.08
    sample_count: int
    accuracy_pct: float | None
    computed_at: datetime | None
    source: str


class SignalFormulaDefaults(BaseModel):
    sentiment_momentum: float
    sentiment_volume: float
    price_momentum: float
    volume_anomaly: float
    earnings: float
    options: float
    analyst: float
    ml: float
    insider: float
    rsi: float
    trend: float
    strong_threshold: float
    moderate_threshold: float
    regime_adjustment: float
    ml_min_accuracy: float
    ml_min_samples: int


class SignalWeightsListResponse(BaseModel):
    defaults: SignalFormulaDefaults
    weights: list[SignalWeightsResponse]


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


class DailyViewOutcome(BaseModel):
    price_change_pct: float
    is_correct: bool


class DailySignalViewResponse(BaseModel):
    ticker: str
    sector: str | None = None
    trading_date: date
    direction: str
    net_score: float
    conviction: float
    signal_count: int
    outcome_1d: DailyViewOutcome | None = None
    outcome_3d: DailyViewOutcome | None = None
    outcome_5d: DailyViewOutcome | None = None
    live_change_pct: float | None = None


class PaginatedDailyViews(BaseModel):
    data: list[DailySignalViewResponse]
    meta: PaginationMeta


class TodaysPredictionsResponse(BaseModel):
    trading_date: date
    data: list[DailySignalViewResponse]


class DailyViewAccuracySummary(BaseModel):
    total_views: int
    evaluated_views: int
    correct: int
    accuracy_pct: float
    avg_conviction: float
    avg_excess_return_correct: float
    avg_excess_return_incorrect: float
    avg_excess_return_all: float
    insufficient_data: bool
    min_views_for_confidence: int


class DailyViewAccuracyTrendBucket(BaseModel):
    week_start: date
    view_count: int
    accuracy_pct: float
    avg_conviction: float
    avg_excess_return: float


class DailyViewAccuracyTrendResponse(BaseModel):
    buckets: list[DailyViewAccuracyTrendBucket]


class DailyViewCalibrationBucket(BaseModel):
    label: str
    min_conviction: float
    max_conviction: float
    count: int
    accuracy_pct: float
    avg_excess_return: float


class DailyViewCalibrationResponse(BaseModel):
    buckets: list[DailyViewCalibrationBucket]


class DailyViewSectorAccuracy(BaseModel):
    sector: str
    count: int
    accuracy_pct: float
    avg_excess_return: float
    avg_conviction: float


class DailyViewSectorAccuracyResponse(BaseModel):
    sectors: list[DailyViewSectorAccuracy]


class DailyViewRegimeAccuracy(BaseModel):
    regime: str
    count: int
    accuracy_pct: float
    avg_excess_return: float
    avg_conviction: float


class DailyViewRegimeAccuracyResponse(BaseModel):
    regimes: list[DailyViewRegimeAccuracy]
