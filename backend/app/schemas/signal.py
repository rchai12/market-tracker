"""Signal and alert schemas for API request/response."""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Pagination ──


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


# ── Signal Schemas ──


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


# ── AlertConfig Schemas ──


class AlertConfigCreate(BaseModel):
    stock_id: int | None = None
    min_strength: str = Field(default="moderate", pattern="^(strong|moderate|weak)$")
    direction_filter: list[str] | None = None
    channel: str = Field(default="both", pattern="^(discord|email|both)$")


class AlertConfigUpdate(BaseModel):
    stock_id: int | None = None
    min_strength: str | None = None
    direction_filter: list[str] | None = None
    channel: str | None = None
    is_active: bool | None = None


class AlertConfigResponse(BaseModel):
    id: int
    user_id: int
    stock_id: int | None
    ticker: str | None = None
    min_strength: str
    direction_filter: list[str] | None
    channel: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── AlertLog Schemas ──


class AlertLogResponse(BaseModel):
    id: int
    signal_id: int
    user_id: int
    channel: str
    sent_at: datetime
    success: bool
    error_message: str | None
    ticker: str | None = None
    direction: str | None = None
    strength: str | None = None

    model_config = {"from_attributes": True}


class PaginatedAlertLogs(BaseModel):
    data: list[AlertLogResponse]
    meta: PaginationMeta


# ── Test Alert ──


class TestAlertRequest(BaseModel):
    channel: str = Field(default="discord", pattern="^(discord|email|both)$")


class TestAlertResponse(BaseModel):
    success: bool
    message: str
