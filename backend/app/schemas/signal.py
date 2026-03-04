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
    price_score: float | None
    volume_score: float | None
    article_count: int
    reasoning: str | None
    generated_at: datetime
    window_start: datetime
    window_end: datetime

    model_config = {"from_attributes": True}


class PaginatedSignals(BaseModel):
    data: list[SignalResponse]
    meta: PaginationMeta
