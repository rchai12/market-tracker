export interface BacktestConfig {
  ticker?: string;
  sector_name?: string;
  start_date: string;
  end_date: string;
  starting_capital?: number;
  mode?: "technical" | "full";
  min_signal_strength?: "moderate" | "strong";
  commission_pct?: number;
  slippage_pct?: number;
  position_size_pct?: number;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  benchmark_ticker?: string;
}

export interface BacktestSummary {
  id: number;
  ticker: string | null;
  sector_name: string | null;
  mode: string;
  status: "pending" | "running" | "completed" | "failed";
  start_date: string;
  end_date: string;
  starting_capital: number;
  min_signal_strength: string;
  commission_pct: number | null;
  slippage_pct: number | null;
  position_size_pct: number | null;
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  benchmark_ticker: string | null;
  total_return_pct: number | null;
  annualized_return_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  win_rate_pct: number | null;
  total_trades: number | null;
  avg_win_pct: number | null;
  avg_loss_pct: number | null;
  best_trade_pct: number | null;
  worst_trade_pct: number | null;
  final_equity: number | null;
  benchmark_total_return_pct: number | null;
  benchmark_annualized_return_pct: number | null;
  alpha: number | null;
  beta: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface BacktestTrade {
  id: number;
  ticker: string;
  action: "buy" | "sell";
  trade_date: string;
  price: number;
  shares: number;
  position_value: number;
  portfolio_equity: number;
  signal_score: number;
  signal_direction: string;
  signal_strength: string;
  return_pct: number | null;
  exit_reason: string | null;
}

export interface BacktestDetail extends BacktestSummary {
  equity_curve: EquityPoint[];
  trades: BacktestTrade[];
  benchmark_equity_curve: EquityPoint[] | null;
}
