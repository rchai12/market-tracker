from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (UniqueConstraint("sector_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True, index=True)
    model_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    training_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_accuracy: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    validation_f1: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    model_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    feature_importances: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_config: Mapped[str | None] = mapped_column(Text, nullable=True)

    sector = relationship("Sector")
