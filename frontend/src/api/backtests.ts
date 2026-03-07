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

export async function exportBacktest(
  id: number,
  type: "trades" | "equity_curve"
): Promise<void> {
  const response = await apiClient.get(`/backtests/${id}/export`, {
    params: { type },
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = `backtest_${id}_${type}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
