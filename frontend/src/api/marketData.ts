import apiClient from "./client";
import type { IndicatorData, MarketDataDaily } from "../types";
import type { EarningsEstimateResponse } from "../types/earnings";
import type { CboePutCallRatio, OptionsActivity } from "../types/options";

export async function getDailyData(
  ticker: string,
  params?: { start_date?: string; end_date?: string; limit?: number }
): Promise<MarketDataDaily[]> {
  const { data } = await apiClient.get(`/market-data/${ticker}/daily`, { params });
  return data;
}

export async function getIndicators(
  ticker: string,
  params?: { days?: number }
): Promise<IndicatorData[]> {
  const { data } = await apiClient.get(`/market-data/${ticker}/indicators`, {
    params,
  });
  return data;
}

export async function getOptionsActivity(
  ticker: string,
  params?: { days?: number }
): Promise<OptionsActivity[]> {
  const { data } = await apiClient.get(`/market-data/${ticker}/options`, { params });
  return data;
}

export async function getCboePutCall(
  params?: { days?: number }
): Promise<CboePutCallRatio[]> {
  const { data } = await apiClient.get("/market-data/cboe/put-call-ratio", { params });
  return data;
}

export async function getEarningsHistory(
  ticker: string,
  limit = 8
): Promise<EarningsEstimateResponse[]> {
  const { data } = await apiClient.get(`/market-data/${ticker}/earnings`, {
    params: { limit },
  });
  return data;
}
