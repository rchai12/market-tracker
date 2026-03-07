from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    __table_args__ = (UniqueConstraint("signal_id", "window_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    outcome_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    price_change_pct: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    signal: Mapped["Signal"] = relationship("Signal", back_populates="outcomes")
