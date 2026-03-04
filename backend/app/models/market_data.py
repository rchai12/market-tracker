from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketDataDaily(Base):
    __tablename__ = "market_data_daily"
    __table_args__ = (UniqueConstraint("stock_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    adj_close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="yfinance")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketDataIntraday(Base):
    __tablename__ = "market_data_intraday"
    __table_args__ = (UniqueConstraint("stock_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
