from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EarningsEstimate(Base):
    __tablename__ = "earnings_estimates"
    __table_args__ = (UniqueConstraint("stock_id", "earnings_date", name="uq_earnings_stock_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    earnings_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    fiscal_quarter: Mapped[str | None] = mapped_column(String(10), nullable=True)
    estimated_eps: Mapped[float | None] = mapped_column(Float(), nullable=True)
    actual_eps: Mapped[float | None] = mapped_column(Float(), nullable=True)
    surprise_pct: Mapped[float | None] = mapped_column(Float(), nullable=True)
    estimated_revenue: Mapped[float | None] = mapped_column(Float(), nullable=True)
    actual_revenue: Mapped[float | None] = mapped_column(Float(), nullable=True)
    revenue_surprise_pct: Mapped[float | None] = mapped_column(Float(), nullable=True)
    guidance_change: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reported: Mapped[bool] = mapped_column(Boolean(), default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock")
