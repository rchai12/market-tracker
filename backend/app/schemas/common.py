"""Shared schema components used across multiple modules."""

import math

from pydantic import BaseModel


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
