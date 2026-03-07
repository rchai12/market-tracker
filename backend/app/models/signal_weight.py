from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SignalWeight(Base):
    __tablename__ = "signal_weights"
    __table_args__ = (UniqueConstraint("sector_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True, index=True)
    sentiment_momentum: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.4)
    sentiment_volume: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.25)
    price_momentum: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.2)
    volume_anomaly: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.15)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sector: Mapped["Sector"] = relationship("Sector")
