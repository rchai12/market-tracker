"""Earnings estimate schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class EarningsEstimateResponse(BaseModel):
    id: int
    earnings_date: date
    fiscal_quarter: str | None
    estimated_eps: float | None
    actual_eps: float | None
    surprise_pct: float | None
    estimated_revenue: float | None
    actual_revenue: float | None
    revenue_surprise_pct: float | None
    guidance_change: str | None
    reported: bool
    fetched_at: datetime

    model_config = {"from_attributes": True}
