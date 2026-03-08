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
