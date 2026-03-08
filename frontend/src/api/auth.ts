import apiClient from "./client";

export interface RegisterPayload {
  email: string;
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    username: string;
    is_active: boolean;
    is_admin: boolean;
  };
}

export async function register(payload: RegisterPayload): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/register", payload);
  return data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const { data } = await apiClient.post<TokenResponse>("/auth/login", formData, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function refreshToken(refreshToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function updateProfile(payload: {
  username?: string;
  email?: string;
}): Promise<TokenResponse["user"]> {
  const { data } = await apiClient.put<TokenResponse["user"]>(
    "/auth/profile",
    payload
  );
  return data;
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<{ message: string }> {
  const { data } = await apiClient.put<{ message: string }>(
    "/auth/password",
    payload
  );
  return data;
}

// ── API Keys ──

export interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface ApiKeyCreateResponse {
  id: number;
  name: string;
  key: string;
  key_prefix: string;
  created_at: string;
}

export async function listApiKeys(): Promise<ApiKey[]> {
  const { data } = await apiClient.get<ApiKey[]>("/auth/api-keys");
  return data;
}

export async function createApiKey(name: string, expiresInDays?: number): Promise<ApiKeyCreateResponse> {
  const { data } = await apiClient.post<ApiKeyCreateResponse>("/auth/api-keys", {
    name,
    expires_in_days: expiresInDays ?? null,
  });
  return data;
}

export async function revokeApiKey(keyId: number): Promise<void> {
  await apiClient.delete(`/auth/api-keys/${keyId}`);
}
