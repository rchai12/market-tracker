from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # bullish, bearish, neutral
    strength: Mapped[str] = mapped_column(String(20), nullable=False)  # strong, moderate, weak
    composite_score: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    price_score: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    volume_score: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    stock = relationship("Stock", back_populates="signals")
    alert_logs = relationship("AlertLog", back_populates="signal")
    outcomes = relationship("SignalOutcome", back_populates="signal", cascade="all, delete-orphan")
