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
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    position_size_pct: float = 100.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    benchmark_ticker: str | None = None

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

    @field_validator("commission_pct")
    @classmethod
    def validate_commission(cls, v: float) -> float:
        if v < 0 or v > 0.05:
            raise ValueError("Commission must be between 0% and 5%")
        return v

    @field_validator("slippage_pct")
    @classmethod
    def validate_slippage(cls, v: float) -> float:
        if v < 0 or v > 0.05:
            raise ValueError("Slippage must be between 0% and 5%")
        return v

    @field_validator("position_size_pct")
    @classmethod
    def validate_position_size(cls, v: float) -> float:
        if v < 10 or v > 100:
            raise ValueError("Position size must be between 10% and 100%")
        return v

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_loss(cls, v: float | None) -> float | None:
        if v is not None and (v <= 0 or v > 50):
            raise ValueError("Stop loss must be between 0% and 50%")
        return v

    @field_validator("take_profit_pct")
    @classmethod
    def validate_take_profit(cls, v: float | None) -> float | None:
        if v is not None and (v <= 0 or v > 500):
            raise ValueError("Take profit must be between 0% and 500%")
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
    exit_reason: str | None = None

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
    commission_pct: float | None = None
    slippage_pct: float | None = None
    position_size_pct: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    benchmark_ticker: str | None = None
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
    benchmark_total_return_pct: float | None = None
    benchmark_annualized_return_pct: float | None = None
    alpha: float | None = None
    beta: float | None = None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BacktestDetailResponse(BacktestResponse):
    equity_curve: list[EquityPointResponse]
    trades: list[BacktestTradeResponse]
    benchmark_equity_curve: list[EquityPointResponse] | None = None


class PaginatedBacktests(BaseModel):
    data: list[BacktestResponse]
    meta: PaginationMeta
