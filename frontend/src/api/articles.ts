import apiClient from "./client";
import type { Article, PaginatedResponse } from "../types";

interface ListArticlesParams {
  page?: number;
  per_page?: number;
  source?: string;
  ticker?: string;
  is_processed?: boolean;
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
