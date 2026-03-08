from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OptionsActivity(Base):
    __tablename__ = "options_activity"
    __table_args__ = (UniqueConstraint("stock_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_call_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_put_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_call_oi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_put_oi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    put_call_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    weighted_avg_iv: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    atm_call_iv: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    atm_put_iv: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    iv_skew: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    expirations_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock")
