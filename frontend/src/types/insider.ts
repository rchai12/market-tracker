export interface InsiderTransaction {
  insider_name: string | null;
  insider_title: string | null;
  transaction_type: string;
  shares: number | null;
  price_per_share: number | null;
  transaction_value: number | null;
  transaction_date: string;
}

export interface InsiderActivity {
  insider_score: number | null;
  window_days: number;
  transactions: InsiderTransaction[];
}
