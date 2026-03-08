export interface OptionsActivity {
  date: string;
  total_call_volume: number | null;
  total_put_volume: number | null;
  total_call_oi: number | null;
  total_put_oi: number | null;
  put_call_ratio: number | null;
  weighted_avg_iv: number | null;
  atm_call_iv: number | null;
  atm_put_iv: number | null;
  iv_skew: number | null;
  expirations_fetched: number;
  data_quality: "full" | "partial" | "stale";
}

export interface CboePutCallRatio {
  date: string;
  total_pc: number | null;
  equity_pc: number | null;
  index_pc: number | null;
}
