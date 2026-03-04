from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), index=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sector = relationship("Sector", back_populates="stocks")
    article_stocks = relationship("ArticleStock", back_populates="stock")
    signals = relationship("Signal", back_populates="stock")
    watchlist_items = relationship("WatchlistItem", back_populates="stock")
