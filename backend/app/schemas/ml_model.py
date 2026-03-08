"""ML model schemas for API responses."""

from datetime import datetime

from pydantic import BaseModel


class MLModelStatusResponse(BaseModel):
    sector_name: str | None
    model_version: int
    training_samples: int
    validation_accuracy: float | None
    validation_f1: float | None
    is_active: bool
    trained_at: datetime | None
    feature_importances: dict[str, float] | None = None

    model_config = {"from_attributes": True}
