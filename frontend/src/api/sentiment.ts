import apiClient from "./client";
import type {
  SentimentScore,
  SentimentSummary,
  SentimentTimePoint,
  PaginatedResponse,
} from "../types";

export async function getTickerSentimentTimeline(
  ticker: string,
  days: number = 30
): Promise<SentimentTimePoint[]> {
  const { data } = await apiClient.get(`/sentiment/${ticker}`, {
    params: { days },
  });
  return data;
}

export async function getTickerSentimentArticles(
  ticker: string,
  page: number = 1,
  per_page: number = 20
): Promise<PaginatedResponse<SentimentScore>> {
  const { data } = await apiClient.get(`/sentiment/${ticker}/articles`, {
    params: { page, per_page },
  });
  return data;
}

export async function getSectorSentiment(
  days: number = 7
): Promise<SentimentSummary[]> {
  const { data } = await apiClient.get("/sentiment/summary/sectors", {
    params: { days },
  });
  return data;
}

export async function getTrendingSentiment(
  days: number = 3,
  limit: number = 10
): Promise<SentimentSummary[]> {
  const { data } = await apiClient.get("/sentiment/trending/stocks", {
    params: { days, limit },
  });
  return data;
}
