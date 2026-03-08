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
