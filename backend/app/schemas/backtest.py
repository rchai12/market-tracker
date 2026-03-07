"""Backtest schemas for API request/response."""

from datetime import date, datetime

from pydantic import BaseModel, field_validator, model_validator

from app.schemas.common import PaginationMeta


class BacktestCreate(BaseModel):
    ticker: str | None = None
    sector_name: str | None = None
    start_date: date
    end_date: date
    starting_capital: float = 10000.0
    mode: str = "technical"
    min_signal_strength: str = "moderate"

    @model_validator(mode="after")
    def validate_target(self):
        if not self.ticker and not self.sector_name:
            raise ValueError("Either ticker or sector_name is required")
        if self.ticker and self.sector_name:
            raise ValueError("Specify either ticker or sector_name, not both")
        return self

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self

    @field_validator("starting_capital")
    @classmethod
    def validate_capital(cls, v: float) -> float:
        if v < 100:
            raise ValueError("Starting capital must be at least $100")
        if v > 1_000_000:
            raise ValueError("Starting capital cannot exceed $1,000,000")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("technical", "full"):
            raise ValueError("Mode must be 'technical' or 'full'")
        return v

    @field_validator("min_signal_strength")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        if v not in ("moderate", "strong"):
            raise ValueError("min_signal_strength must be 'moderate' or 'strong'")
        return v


class EquityPointResponse(BaseModel):
    date: str
    equity: float


class BacktestTradeResponse(BaseModel):
    id: int
    ticker: str
    action: str
    trade_date: datetime
    price: float
    shares: float
    position_value: float
    portfolio_equity: float
    signal_score: float
    signal_direction: str
    signal_strength: str
    return_pct: float | None

    model_config = {"from_attributes": True}


class BacktestResponse(BaseModel):
    id: int
    ticker: str | None = None
    sector_name: str | None = None
    mode: str
    status: str
    start_date: datetime
    end_date: datetime
    starting_capital: float
    min_signal_strength: str
    total_return_pct: float | None
    annualized_return_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    win_rate_pct: float | None
    total_trades: int | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    final_equity: float | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BacktestDetailResponse(BacktestResponse):
    equity_curve: list[EquityPointResponse]
    trades: list[BacktestTradeResponse]


class PaginatedBacktests(BaseModel):
    data: list[BacktestResponse]
    meta: PaginationMeta
