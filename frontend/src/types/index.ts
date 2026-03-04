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
  market_cap: number | null;
  is_active: boolean;
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
