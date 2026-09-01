export interface EarningsEstimateResponse {
  id: number;
  earnings_date: string;
  fiscal_quarter: string | null;
  estimated_eps: number | null;
  actual_eps: number | null;
  surprise_pct: number | null;
  estimated_revenue: number | null;
  actual_revenue: number | null;
  revenue_surprise_pct: number | null;
  guidance_change: string | null;
  reported: boolean;
  fetched_at: string;
}
