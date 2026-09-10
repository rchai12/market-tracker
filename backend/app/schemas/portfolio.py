"""Paper portfolio API schemas."""

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class PortfolioSummary(BaseModel):
    inception_date: date
    starting_capital: float
    current_cash: float
    cash_pct: float
    total_value: float
    total_return_pct: float
    benchmark_return_pct: float | None = None
    open_positions: int
    benchmark_ticker: str


class PortfolioPosition(BaseModel):
    id: int
    stock_id: int
    ticker: str
    company_name: str
    sector: str | None = None
    opened_at: datetime
    entry_price: float
    current_price: float | None = None
    shares: float
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None

    model_config = {"from_attributes": True}


class PortfolioTrade(BaseModel):
    id: int
    ticker: str
    opened_at: datetime
    closed_at: datetime
    entry_price: float
    exit_price: float
    shares: float
    realized_pnl: float
    return_pct: float
    exit_reason: str

    model_config = {"from_attributes": True}


class PaginatedTrades(BaseModel):
    data: list[PortfolioTrade]
    meta: PaginationMeta


class PortfolioSnapshot(BaseModel):
    date: date
    total_value: float
    benchmark_value: float | None = None

    model_config = {"from_attributes": True}


class PortfolioPerformance(BaseModel):
    starting_capital: float
    points: list[PortfolioSnapshot]


class PortfolioStats(BaseModel):
    sharpe_ratio: float | None = None
    max_drawdown_pct: float | None = None
    win_rate_pct: float | None = None
    avg_win_pct: float | None = None
    avg_loss_pct: float | None = None
    alpha: float | None = None
    beta: float | None = None
    total_trades: int = 0
