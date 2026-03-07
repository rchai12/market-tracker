from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Backtest(Base):
    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id"), nullable=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # technical, full
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    starting_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=10000)
    min_signal_strength: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")

    # Result metrics (populated on completion)
    total_return_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    annualized_return_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    win_rate_pct: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_win_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    avg_loss_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    best_trade_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    worst_trade_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    final_equity: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Equity curve as JSON (written once on completion)
    equity_curve: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    stock = relationship("Stock")
    sector = relationship("Sector")
    trades = relationship("BacktestTrade", back_populates="backtest", cascade="all, delete-orphan")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    backtest_id: Mapped[int] = mapped_column(
        ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # buy, sell
    trade_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    shares: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    position_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    portfolio_equity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    signal_score: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    signal_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    return_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

    backtest = relationship("Backtest", back_populates="trades")
