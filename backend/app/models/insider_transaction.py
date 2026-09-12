from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InsiderTransaction(Base):
    __tablename__ = "insider_transactions"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "insider_name",
            "transaction_date",
            "transaction_type",
            "shares",
            name="uq_insider_tx_dedup",
        ),
        Index("idx_insider_stock_date", "stock_id", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    insider_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insider_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)  # P, S, A, D
    shares: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    price_per_share: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    transaction_value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", back_populates="insider_transactions")
