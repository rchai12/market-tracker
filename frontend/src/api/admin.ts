import apiClient from "./client";

export interface TaskResponse {
  task_id: string;
  status: string;
  period?: string;
}

export interface DbTableStats {
  table: string;
  estimated_rows: number;
  total_size: string;
  total_size_bytes: number;
}

export interface DbStatsResponse {
  tables: DbTableStats[];
  total_size: string;
  total_size_bytes: number;
}

export async function triggerScrape(): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>("/admin/scrape-now");
  return data;
}

export async function triggerSeedHistory(period: string = "max"): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>(`/admin/seed-history?period=${period}`);
  return data;
}

export async function triggerMaintenance(): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>("/admin/maintenance");
  return data;
}

export async function triggerOutcomeEval(): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>("/admin/evaluate-outcomes");
  return data;
}

export async function triggerWeightCompute(): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>("/admin/compute-weights");
  return data;
}

export async function getDbStats(): Promise<DbStatsResponse> {
  const { data } = await apiClient.get<DbStatsResponse>("/admin/db-stats");
  return data;
}
