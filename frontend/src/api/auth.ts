import { fetchJson, postJson } from "@/lib/apiClient";

export type LoginResponse = {
  expiresIn: number;
  email: string;
  isAdmin: boolean;
};

export type MeResponse = {
  email: string;
  isAdmin: boolean;
};

export type AuthResult = {
  success: boolean;
  error?: string;
};

export const getCurrentUser = (apiBaseUrl: string, signal?: AbortSignal) =>
  fetchJson<MeResponse>(`${apiBaseUrl}/auth/me`, {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

export const loginUser = async (
  apiBaseUrl: string,
  email: string,
  password: string
): Promise<AuthResult & { email?: string }> => {
  const result = await postJson<LoginResponse>(`${apiBaseUrl}/auth/login`, {
    body: { email, password },
    errorFallback: (status) =>
      status === 429 ? "Too many login attempts. Try again later." : "Invalid email or password.",
    networkError: "Unable to reach authentication service.",
  });
  return result.ok
    ? { success: true, email: result.data.email }
    : { success: false, error: result.error };
};

export const logoutUser = (apiBaseUrl: string) =>
  fetch(`${apiBaseUrl}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });

