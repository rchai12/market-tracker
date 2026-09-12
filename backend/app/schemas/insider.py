"""Insider activity schemas for API response."""

from datetime import date

from pydantic import BaseModel


class InsiderTransactionResponse(BaseModel):
    insider_name: str | None
    insider_title: str | None
    transaction_type: str
    shares: float | None
    price_per_share: float | None
    transaction_value: float | None
    transaction_date: date

    model_config = {"from_attributes": True}


class InsiderActivityResponse(BaseModel):
    insider_score: float | None
    window_days: int
    transactions: list[InsiderTransactionResponse]
