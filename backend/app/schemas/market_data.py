from datetime import date, datetime

from pydantic import BaseModel


class MarketDataDailyResponse(BaseModel):
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    adj_close: float | None
    volume: int | None

    model_config = {"from_attributes": True}


class MarketDataIntradayResponse(BaseModel):
    timestamp: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None

    model_config = {"from_attributes": True}
