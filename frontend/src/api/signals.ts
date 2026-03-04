import apiClient from "./client";
import type { Signal, PaginatedResponse } from "../types";

export async function getLatestSignals(
  limit: number = 20,
  minStrength?: string
): Promise<Signal[]> {
  const { data } = await apiClient.get("/signals/latest", {
    params: { limit, min_strength: minStrength },
  });
  return data;
}

export async function listSignals(params?: {
  page?: number;
  per_page?: number;
  direction?: string;
  strength?: string;
  ticker?: string;
}): Promise<PaginatedResponse<Signal>> {
  const { data } = await apiClient.get("/signals", { params });
  return data;
}

export async function getSignalHistory(
  ticker: string,
  page: number = 1,
  per_page: number = 20
): Promise<PaginatedResponse<Signal>> {
  const { data } = await apiClient.get(`/signals/${ticker}`, {
    params: { page, per_page },
  });
  return data;
}
