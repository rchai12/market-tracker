from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id"), nullable=True)
    min_strength: Mapped[str] = mapped_column(String(20), default="moderate")
    direction_filter: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="both")  # discord, email, both
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="alert_configs")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    signal = relationship("Signal", back_populates="alert_logs")
