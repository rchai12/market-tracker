import apiClient from "./client";
import type {
  Signal,
  SignalAccuracy,
  SignalWeightsPayload,
  AccuracyTrendPoint,
  AccuracyDistribution,
  SignalDetail,
  DailySignalView,
  TodaysPredictions,
  DailyViewAccuracySummary,
  DailyViewAccuracyTrendBucket,
  DailyViewCalibrationBucket,
  DailyViewSectorAccuracy,
  DailyViewRegimeAccuracy,
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

export async function getSignalWeights(): Promise<SignalWeightsPayload> {
  const { data } = await apiClient.get("/signals/weights");
  return data;
}

export async function getMLAccuracy(params?: {
  window_days?: number;
  sector?: string;
  days?: number;
}): Promise<SignalAccuracy[]> {
  const { data } = await apiClient.get("/signals/accuracy/ml", { params });
  return data;
}

export async function getDailyViews(params?: {
  page?: number;
  per_page?: number;
  date?: string;
  sector?: string;
  direction?: string;
  min_conviction?: number;
}): Promise<PaginatedResponse<DailySignalView>> {
  const { data } = await apiClient.get("/signals/daily-views", { params });
  return data;
}

export async function getTodaysPredictions(): Promise<TodaysPredictions> {
  const { data } = await apiClient.get("/signals/daily-views/today");
  return data;
}

export interface DailyViewAccuracyParams {
  window_days?: number;
  sector?: string;
  direction?: string;
  date_from?: string;
  date_to?: string;
  min_conviction?: number;
}

export async function getDailyViewAccuracy(
  params?: DailyViewAccuracyParams
): Promise<DailyViewAccuracySummary> {
  const { data } = await apiClient.get("/signals/daily-views/accuracy", { params });
  return data;
}

export async function getDailyViewAccuracyTrend(
  params?: DailyViewAccuracyParams
): Promise<{ buckets: DailyViewAccuracyTrendBucket[] }> {
  const { data } = await apiClient.get("/signals/daily-views/accuracy/trend", { params });
  return data;
}

export async function getDailyViewCalibration(
  params?: DailyViewAccuracyParams
): Promise<{ buckets: DailyViewCalibrationBucket[] }> {
  const { data } = await apiClient.get("/signals/daily-views/accuracy/calibration", { params });
  return data;
}

export async function getDailyViewSectorAccuracy(
  params?: DailyViewAccuracyParams
): Promise<{ sectors: DailyViewSectorAccuracy[] }> {
  const { data } = await apiClient.get("/signals/daily-views/accuracy/sectors", { params });
  return data;
}

export async function getDailyViewRegimeAccuracy(
  params?: DailyViewAccuracyParams
): Promise<{ regimes: DailyViewRegimeAccuracy[] }> {
  const { data } = await apiClient.get("/signals/daily-views/accuracy/regimes", { params });
  return data;
}

export function isoDateDaysAgo(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

