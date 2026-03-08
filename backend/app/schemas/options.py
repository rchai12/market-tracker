"""Options flow schemas for API response."""

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class OptionsActivityResponse(BaseModel):
    date: date
    total_call_volume: int | None
    total_put_volume: int | None
    total_call_oi: int | None
    total_put_oi: int | None
    put_call_ratio: float | None
    weighted_avg_iv: float | None
    atm_call_iv: float | None
    atm_put_iv: float | None
    iv_skew: float | None
    expirations_fetched: int
    data_quality: str

    model_config = {"from_attributes": True}


class PaginatedOptionsActivity(BaseModel):
    data: list[OptionsActivityResponse]
    meta: PaginationMeta


class CboePutCallResponse(BaseModel):
    date: date
    total_pc: float | None
    equity_pc: float | None
    index_pc: float | None

    model_config = {"from_attributes": True}
