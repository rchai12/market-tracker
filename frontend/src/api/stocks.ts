import apiClient from "./client";
import type { PaginatedResponse, Stock } from "../types";

export async function listStocks(params?: {
  sector?: string;
  search?: string;
  page?: number;
  per_page?: number;
}): Promise<PaginatedResponse<Stock>> {
  const { data } = await apiClient.get("/stocks", { params });
  return data;
}

export async function getStock(ticker: string): Promise<Stock> {
  const { data } = await apiClient.get(`/stocks/${ticker}`);
  return data;
}
