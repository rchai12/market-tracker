import apiClient from "./client";
import type { Article, EventCategorySummary, PaginatedResponse } from "../types";

interface ListArticlesParams {
  page?: number;
  per_page?: number;
  source?: string;
  ticker?: string;
  is_processed?: boolean;
  event_category?: string;
}

export async function listArticles(
  params: ListArticlesParams = {}
): Promise<PaginatedResponse<Article>> {
  const { data } = await apiClient.get("/articles", { params });
  return data;
}

export async function listSources(): Promise<
  { source: string; count: number }[]
> {
  const { data } = await apiClient.get("/articles/sources");
  return data;
}

export async function getEventCategories(): Promise<EventCategorySummary[]> {
  const { data } = await apiClient.get("/articles/event-categories");
  return data;
}
