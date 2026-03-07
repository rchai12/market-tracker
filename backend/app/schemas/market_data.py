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


class IndicatorDataResponse(BaseModel):
    date: date
    sma20: float | None = None
    sma50: float | None = None
    rsi: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None


class MarketDataIntradayResponse(BaseModel):
    timestamp: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None

    model_config = {"from_attributes": True}
