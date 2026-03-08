export interface User {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
}

export interface Stock {
  id: number;
  ticker: string;
  company_name: string;
  sector_id: number | null;
  sector_name: string | null;
  market_cap: number | null;
  is_active: boolean;
  latest_sentiment: string | null;
  latest_signal_direction: string | null;
  latest_signal_strength: string | null;
}

export interface Article {
  id: number;
  source: string;
  source_url: string | null;
  title: string;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  scraped_at: string;
  is_processed: boolean;
  event_category: string | null;
}

export interface SentimentScore {
  id: number;
  article_id: number;
  stock_id: number | null;
  label: "positive" | "negative" | "neutral";
  positive_score: number;
  negative_score: number;
  neutral_score: number;
  processed_at: string;
  article_title?: string;
  article_source?: string;
  article_source_url?: string;
}

export interface SentimentSummary {
  ticker: string | null;
  sector: string | null;
  total_articles: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  avg_positive: number;
  avg_negative: number;
  avg_neutral: number;
  dominant_label: string;
}

export interface SentimentTimePoint {
  date: string;
  avg_positive: number;
  avg_negative: number;
  avg_neutral: number;
  article_count: number;
  dominant_label: string;
}

export interface Signal {
  id: number;
  stock_id: number;
  ticker: string;
  company_name: string;
  direction: "bullish" | "bearish" | "neutral";
  strength: "strong" | "moderate" | "weak";
  composite_score: number;
  sentiment_score: number | null;
  sentiment_volume_score: number | null;
  price_score: number | null;
  volume_score: number | null;
  rsi_score: number | null;
  trend_score: number | null;
  article_count: number;
  reasoning: string | null;
  generated_at: string;
  window_start: string;
  window_end: string;
}

export interface AccuracyTrendPoint {
  period_start: string;
  period_end: string;
  total: number;
  correct: number;
  accuracy_pct: number;
}

export interface AccuracyBucket {
  label: string;
  total: number;
  correct: number;
  accuracy_pct: number;
  avg_return_pct: number;
}

export interface AccuracyDistribution {
  by_strength: AccuracyBucket[];
  by_direction: AccuracyBucket[];
}

export interface SignalOutcome {
  window_days: number;
  price_change_pct: number;
  is_correct: boolean;
  evaluated_at: string;
}

export interface LinkedArticle {
  id: number;
  title: string;
  source: string;
  url: string | null;
  published_at: string | null;
  sentiment_label: string | null;
  sentiment_score: number | null;
}

export interface SignalDetail {
  signal: Signal;
  outcomes: SignalOutcome[];
  linked_articles: LinkedArticle[];
}

export interface AlertConfig {
  id: number;
  user_id: number;
  stock_id: number | null;
  ticker: string | null;
  min_strength: "strong" | "moderate" | "weak";
  direction_filter: string[] | null;
  channel: "discord" | "email" | "both";
  is_active: boolean;
  created_at: string;
}

export interface AlertLog {
  id: number;
  signal_id: number;
  user_id: number;
  channel: string;
  sent_at: string;
  success: boolean;
  error_message: string | null;
  ticker: string | null;
  direction: string | null;
  strength: string | null;
}

export interface MarketDataDaily {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SignalAccuracy {
  scope: string;
  window_days: number;
  total_evaluated: number;
  correct_count: number;
  accuracy_pct: number;
  avg_return_correct: number;
  avg_return_wrong: number;
  bullish_accuracy_pct: number | null;
  bearish_accuracy_pct: number | null;
}

export interface SignalWeights {
  sector_name: string | null;
  sentiment_momentum: number;
  sentiment_volume: number;
  price_momentum: number;
  volume_anomaly: number;
  rsi: number;
  trend: number;
  sample_count: number;
  accuracy_pct: number | null;
  computed_at: string | null;
  source: string;
}

export interface IndicatorData {
  date: string;
  sma20: number | null;
  sma50: number | null;
  rsi: number | null;
  macd_line: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  bb_upper: number | null;
  bb_middle: number | null;
  bb_lower: number | null;
}

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

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}
