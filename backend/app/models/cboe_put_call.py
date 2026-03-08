from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CboePutCallRatio(Base):
    __tablename__ = "cboe_put_call_ratio"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_pc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    equity_pc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    index_pc: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
