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
  article_event_category?: string;
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
