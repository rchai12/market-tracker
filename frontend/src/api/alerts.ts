import apiClient from "./client";
import type { AlertConfig, AlertLog, PaginatedResponse } from "../types";

export async function getAlertConfigs(): Promise<AlertConfig[]> {
  const { data } = await apiClient.get("/alerts/configs");
  return data;
}

export async function createAlertConfig(config: {
  stock_id?: number | null;
  min_strength?: string;
  direction_filter?: string[] | null;
  channel?: string;
}): Promise<AlertConfig> {
  const { data } = await apiClient.post("/alerts/configs", config);
  return data;
}

export async function updateAlertConfig(
  id: number,
  updates: {
    stock_id?: number | null;
    min_strength?: string;
    direction_filter?: string[] | null;
    channel?: string;
    is_active?: boolean;
  }
): Promise<AlertConfig> {
  const { data } = await apiClient.put(`/alerts/configs/${id}`, updates);
  return data;
}

export async function deleteAlertConfig(id: number): Promise<void> {
  await apiClient.delete(`/alerts/configs/${id}`);
}

export async function getAlertHistory(
  page: number = 1,
  per_page: number = 20
): Promise<PaginatedResponse<AlertLog>> {
  const { data } = await apiClient.get("/alerts/history", {
    params: { page, per_page },
  });
  return data;
}

export async function sendTestAlert(channel: string = "discord"): Promise<{
  success: boolean;
  message: string;
}> {
  const { data } = await apiClient.post("/alerts/test", { channel });
  return data;
}
