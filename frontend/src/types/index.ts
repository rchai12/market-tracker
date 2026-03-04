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
  direction: "bullish" | "bearish" | "neutral";
  strength: "strong" | "moderate" | "weak";
  composite_score: number;
  reasoning: string | null;
  generated_at: string;
}

export interface MarketDataDaily {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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
