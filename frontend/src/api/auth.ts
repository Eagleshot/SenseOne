import { extractErrorDetail, fetchJson } from "@/lib/apiClient";

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
  try {
    const response = await fetch(`${apiBaseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "include",
    });

    if (!response.ok) {
      const fallback =
        response.status === 429
          ? "Too many login attempts. Try again later."
          : "Invalid email or password.";
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
    return { success: true, email: payload.email };
  } catch {
    return { success: false, error: "Unable to reach authentication service." };
  }
};

export const logoutUser = (apiBaseUrl: string) =>
  fetch(`${apiBaseUrl}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });

