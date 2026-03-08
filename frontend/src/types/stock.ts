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

export interface MarketDataDaily {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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
