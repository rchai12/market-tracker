import apiClient from "./client";
import type { PaginatedResponse } from "../types";
import type {
  PortfolioPerformance,
  PortfolioPosition,
  PortfolioStats,
  PortfolioSummary,
  PortfolioTrade,
} from "../types/portfolio";

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  const { data } = await apiClient.get("/portfolio/summary");
  return data;
}

export async function getPortfolioPositions(): Promise<PortfolioPosition[]> {
  const { data } = await apiClient.get("/portfolio/positions");
  return data;
}

export async function getPortfolioTrades(
  page = 1,
  per_page = 20
): Promise<PaginatedResponse<PortfolioTrade>> {
  const { data } = await apiClient.get("/portfolio/trades", { params: { page, per_page } });
  return data;
}

export async function getPortfolioPerformance(): Promise<PortfolioPerformance> {
  const { data } = await apiClient.get("/portfolio/performance");
  return data;
}

export async function getPortfolioStats(): Promise<PortfolioStats> {
  const { data } = await apiClient.get("/portfolio/stats");
  return data;
}
