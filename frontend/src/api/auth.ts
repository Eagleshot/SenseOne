import { extractErrorDetail, fetchJson } from "@/lib/apiClient";

export type LoginResponse = {
  expiresIn: number;
  username: string;
  isAdmin: boolean;
};

export type MeResponse = {
  username: string;
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
  username: string,
  password: string
): Promise<AuthResult & { username?: string }> => {
  try {
    const response = await fetch(`${apiBaseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      credentials: "include",
    });

    if (!response.ok) {
      const fallback =
        response.status === 429
          ? "Too many login attempts. Try again later."
          : "Invalid username or password.";
      let message = fallback;

      try {
        const payload = await response.json();
        message = extractErrorDetail(payload, fallback);
      } catch {
        // Keep fallback when response body is not JSON.
      }

      return { success: false, error: message };
    }

    const payload = (await response.json()) as LoginResponse;
    return { success: true, username: payload.username };
  } catch {
    return { success: false, error: "Unable to reach authentication service." };
  }
};

export const logoutUser = (apiBaseUrl: string) =>
  fetch(`${apiBaseUrl}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
