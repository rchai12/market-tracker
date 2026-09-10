from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    inception_date: Mapped[date] = mapped_column(Date, nullable=False)
    starting_capital: Mapped[float] = mapped_column(Float, nullable=False)
    current_cash: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    benchmark_ticker: Mapped[str] = mapped_column(String(10), default="SPY", nullable=False)
    benchmark_inception_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    positions = relationship("PaperPosition", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("PaperTrade", back_populates="portfolio", cascade="all, delete-orphan")
    snapshots = relationship("PaperPortfolioSnapshot", back_populates="portfolio", cascade="all, delete-orphan")


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("portfolio_id", "stock_id", name="uq_paper_position_stock"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    entry_signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    portfolio = relationship("PaperPortfolio", back_populates="positions")
    stock = relationship("Stock")


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    entry_signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    exit_signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(30), nullable=False)

    portfolio = relationship("PaperPortfolio", back_populates="trades")
    stock = relationship("Stock")


class PaperPortfolioSnapshot(Base):
    __tablename__ = "paper_portfolio_snapshots"
    __table_args__ = (UniqueConstraint("portfolio_id", "snapshot_date", name="uq_paper_snapshot_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    equity_value: Mapped[float] = mapped_column(Float, nullable=False)
    open_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    benchmark_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cumulative_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_cumulative_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    portfolio = relationship("PaperPortfolio", back_populates="snapshots")
