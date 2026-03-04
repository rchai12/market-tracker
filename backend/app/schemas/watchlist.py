from datetime import datetime

from pydantic import BaseModel


class WatchlistAdd(BaseModel):
    ticker: str


class WatchlistItemResponse(BaseModel):
    id: int
    stock_id: int
    ticker: str
    company_name: str
    sector_name: str | None = None
    added_at: datetime

    model_config = {"from_attributes": True}
