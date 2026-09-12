from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RegimeAdaptiveWeight(Base):
    """Per-(sector, regime) adaptive component weights learned from outcomes."""

    __tablename__ = "regime_adaptive_weights"
    __table_args__ = (
        UniqueConstraint(
            "sector_id",
            "regime",
            name="uq_regime_adaptive_weights_sector_regime",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True, index=True)
    regime: Mapped[str] = mapped_column(String(20), nullable=False)
    sentiment_momentum: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    sentiment_volume: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    price_momentum: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    volume_anomaly: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    earnings: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.10)
    options: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.08)
    analyst: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.07)
    insider: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.08)
    rsi: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    trend: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sector = relationship("Sector")
