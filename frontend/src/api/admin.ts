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

export interface MLModelStatus {
  sector_name: string | null;
  model_version: number;
  training_samples: number;
  validation_accuracy: number | null;
  validation_f1: number | null;
  is_active: boolean;
  trained_at: string | null;
  feature_importances: Record<string, number> | null;
}

export async function triggerOptionsFetch(): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>("/admin/fetch-options");
  return data;
}

export async function triggerMLTraining(): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>("/admin/train-ml-models");
  return data;
}

export async function getMLModelStatus(): Promise<MLModelStatus[]> {
  const { data } = await apiClient.get<MLModelStatus[]>("/admin/ml-models");
  return data;
}

// ── Task Failures (Dead Letter Queue) ──

export interface TaskFailure {
  id: number;
  task_name: string;
  task_args: string | null;
  task_kwargs: string | null;
  exception_type: string | null;
  exception_message: string | null;
  retries_exhausted: boolean;
  failed_at: string;
  retried_at: string | null;
  retry_task_id: string | null;
}

export interface PaginatedTaskFailures {
  data: TaskFailure[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export async function getTaskFailures(page = 1, perPage = 10): Promise<PaginatedTaskFailures> {
  const { data } = await apiClient.get<PaginatedTaskFailures>(
    `/admin/task-failures?page=${page}&per_page=${perPage}`
  );
  return data;
}

export async function retryFailedTask(failureId: number): Promise<TaskResponse> {
  const { data } = await apiClient.post<TaskResponse>(`/admin/task-failures/${failureId}/retry`);
  return data;
}

// ── Audit Logs ──

export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  action: string;
  resource: string;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface PaginatedAuditLogs {
  data: AuditLogEntry[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export async function getAuditLog(page = 1, perPage = 10): Promise<PaginatedAuditLogs> {
  const { data } = await apiClient.get<PaginatedAuditLogs>(
    `/admin/audit-log?page=${page}&per_page=${perPage}`
  );
  return data;
}
