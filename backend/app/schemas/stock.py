from pydantic import BaseModel


class SectorResponse(BaseModel):
    id: int
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class StockResponse(BaseModel):
    id: int
    ticker: str
    company_name: str
    sector_id: int | None
    sector_name: str | None = None
    market_cap: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class StockDetailResponse(StockResponse):
    latest_sentiment: str | None = None
    latest_signal_direction: str | None = None
    latest_signal_strength: str | None = None


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedStocks(BaseModel):
    data: list[StockResponse]
    meta: PaginationMeta
