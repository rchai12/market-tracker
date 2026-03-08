"""Schemas for API key management."""

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Label for this API key")
    expires_in_days: int | None = Field(None, ge=1, le=365, description="Optional expiry in days")


class ApiKeyCreateResponse(BaseModel):
    """Returned once at creation — the only time the raw key is visible."""

    id: int
    name: str
    key: str
    key_prefix: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Public listing (no raw key)."""

    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
