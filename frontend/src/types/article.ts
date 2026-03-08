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
  duplicate_group_id: number | null;
}

export interface EventCategorySummary {
  category: string;
  count: number;
}
