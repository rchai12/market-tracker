import apiClient from "./client";
import type { MarketDataDaily } from "../types";

export async function getDailyData(
  ticker: string,
  params?: { start_date?: string; end_date?: string; limit?: number }
): Promise<MarketDataDaily[]> {
  const { data } = await apiClient.get(`/market-data/${ticker}/daily`, { params });
  return data;
}
