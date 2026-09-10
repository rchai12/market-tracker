export interface PortfolioSummary {
  inception_date: string;
  starting_capital: number;
  current_cash: number;
  cash_pct: number;
  total_value: number;
  total_return_pct: number;
  benchmark_return_pct: number | null;
  open_positions: number;
  benchmark_ticker: string;
}

export interface PortfolioPosition {
  id: number;
  stock_id: number;
  ticker: string;
  company_name: string;
  sector: string | null;
  opened_at: string;
  entry_price: number;
  current_price: number | null;
  shares: number;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  stop_loss_price: number | null;
  take_profit_price: number | null;
}

export interface PortfolioTrade {
  id: number;
  ticker: string;
  opened_at: string;
  closed_at: string;
  entry_price: number;
  exit_price: number;
  shares: number;
  realized_pnl: number;
  return_pct: number;
  exit_reason: string;
}

export interface PortfolioSnapshot {
  date: string;
  total_value: number;
  benchmark_value: number | null;
}

export interface PortfolioPerformance {
  starting_capital: number;
  points: PortfolioSnapshot[];
}

export interface PortfolioStats {
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  win_rate_pct: number | null;
  avg_win_pct: number | null;
  avg_loss_pct: number | null;
  alpha: number | null;
  beta: number | null;
  total_trades: number;
}
