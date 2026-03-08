import apiClient from "./client";
import type {
  Signal,
  SignalAccuracy,
  SignalWeights,
  AccuracyTrendPoint,
  AccuracyDistribution,
  SignalDetail,
  PaginatedResponse,
} from "../types";

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
  sector?: string;
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

export async function getSignalAccuracy(params?: {
  window_days?: number;
  sector?: string;
  days?: number;
}): Promise<SignalAccuracy[]> {
  const { data } = await apiClient.get("/signals/accuracy", { params });
  return data;
}

export async function getTickerAccuracy(
  ticker: string,
  days: number = 90
): Promise<SignalAccuracy[]> {
  const { data } = await apiClient.get(`/signals/accuracy/${ticker}`, {
    params: { days },
  });
  return data;
}

export async function getAccuracyTrend(params?: {
  window_days?: number;
  sector?: string;
  bucket?: string;
  days?: number;
}): Promise<AccuracyTrendPoint[]> {
  const { data } = await apiClient.get("/signals/accuracy/trend", { params });
  return data;
}

export async function getAccuracyDistribution(params?: {
  window_days?: number;
  days?: number;
}): Promise<AccuracyDistribution> {
  const { data } = await apiClient.get("/signals/accuracy/distribution", {
    params,
  });
  return data;
}

export async function getSignalDetail(
  signalId: number
): Promise<SignalDetail> {
  const { data } = await apiClient.get(`/signals/detail/${signalId}`);
  return data;
}

export async function getSignalWeights(): Promise<SignalWeights[]> {
  const { data } = await apiClient.get("/signals/weights");
  return data;
}
