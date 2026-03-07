import apiClient from "./client";
import type {
  BacktestConfig,
  BacktestDetail,
  BacktestSummary,
  PaginatedResponse,
} from "../types";

export async function createBacktest(
  config: BacktestConfig
): Promise<BacktestSummary> {
  const { data } = await apiClient.post("/backtests", config);
  return data;
}

export async function listBacktests(params?: {
  page?: number;
  per_page?: number;
  status?: string;
}): Promise<PaginatedResponse<BacktestSummary>> {
  const { data } = await apiClient.get("/backtests", { params });
  return data;
}

export async function getBacktest(id: number): Promise<BacktestDetail> {
  const { data } = await apiClient.get(`/backtests/${id}`);
  return data;
}

export async function deleteBacktest(id: number): Promise<void> {
  await apiClient.delete(`/backtests/${id}`);
}
