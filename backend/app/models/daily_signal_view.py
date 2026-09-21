"""Daily net signal views (Phase 24) — one row per stock per trading session."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailySignalView(Base):
    __tablename__ = "daily_signal_views"
    __table_args__ = (UniqueConstraint("stock_id", "trading_date", name="uq_daily_signal_views_stock_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    net_score: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    conviction: Mapped[float] = mapped_column(Float, nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    baseline_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    stock = relationship("Stock", back_populates="daily_signal_views")
    outcomes = relationship(
        "DailySignalViewOutcome", back_populates="daily_view", cascade="all, delete-orphan"
    )


class DailySignalViewOutcome(Base):
    __tablename__ = "daily_signal_view_outcomes"
    __table_args__ = (UniqueConstraint("daily_view_id", "window_days", name="uq_daily_view_outcome_window"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_view_id: Mapped[int] = mapped_column(
        ForeignKey("daily_signal_views.id", ondelete="CASCADE"), nullable=False, index=True
    )
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome_close: Mapped[float] = mapped_column(Float, nullable=False)
    price_change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    daily_view = relationship("DailySignalView", back_populates="outcomes")
