"""Shared schema components used across multiple modules."""

import math

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


def calc_total_pages(total: int, per_page: int) -> int:
    """Calculate total pages for pagination. Returns 0 for empty results."""
    if total <= 0:
        return 0
    return math.ceil(total / per_page)


async def get_total_count(db: AsyncSession, query: Select) -> int:
    """Get total row count for a query (for pagination)."""
    count_query = select(func.count()).select_from(query.subquery())
    return (await db.execute(count_query)).scalar() or 0


class PaginationParams:
    """FastAPI dependency for pagination query parameters.

    Usage::

        async def list_items(
            pagination: PaginationParams = Depends(),
            db: AsyncSession = Depends(get_db),
        ):
            query = base_query.offset(pagination.offset).limit(pagination.per_page)
    """

    def __init__(
        self,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
    ):
        self.page = page
        self.per_page = per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page
