import apiClient from "./client";

export interface WatchlistItem {
  id: number;
  stock_id: number;
  ticker: string;
  company_name: string;
  sector_name: string | null;
  added_at: string;
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  const { data } = await apiClient.get("/watchlist");
  return data;
}

export async function addToWatchlist(ticker: string): Promise<WatchlistItem> {
  const { data } = await apiClient.post("/watchlist", { ticker });
  return data;
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await apiClient.delete(`/watchlist/${ticker}`);
}
