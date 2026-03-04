"""Article schemas for API responses."""

from datetime import datetime

from pydantic import BaseModel


class ArticleResponse(BaseModel):
    id: int
    source: str
    source_url: str | None
    title: str
    summary: str | None
    author: str | None
    published_at: datetime | None
    scraped_at: datetime
    is_processed: bool
    event_category: str | None
    tickers: list[str] = []

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedArticles(BaseModel):
    data: list[ArticleResponse]
    meta: PaginationMeta
