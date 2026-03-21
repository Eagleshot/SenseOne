import { useEffect, useState } from "react";

import { removeStoredValue } from "@/lib/storage";

import { fetchJson, isAbortError, LoginResponse, MeResponse } from "./appContextUtils";

type AuthResult = {
  success: boolean;
  error?: string;
};

export type AuthSessionState = {
  isAuthenticated: boolean;
  authenticatedUsername: string | null;
  authReady: boolean;
  login: (username: string, password: string) => Promise<AuthResult>;
  logout: () => Promise<void>;
};

export const useAuthSession = (apiBaseUrl: string): AuthSessionState => {
  const [authenticatedUsername, setAuthenticatedUsername] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const isAuthenticated = authReady && Boolean(authenticatedUsername);

  useEffect(() => {
    removeStoredValue("authToken");
    removeStoredValue("authUsername");
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const validateSession = async () => {
      try {
        const payload = await fetchJson<MeResponse>(`${apiBaseUrl}/auth/me`, {
          credentials: "include",
          signal: controller.signal,
          throwOnHttpError: false,
        });

        if (controller.signal.aborted) return;
        setAuthenticatedUsername(payload?.username ?? null);
      } catch (error) {
        if (isAbortError(error)) return;
        setAuthenticatedUsername(null);
      } finally {
        if (!controller.signal.aborted) {
          setAuthReady(true);
        }
      }
    };

    void validateSession();

    return () => {
      controller.abort();
    };
  }, [apiBaseUrl]);

  const login = async (username: string, password: string): Promise<AuthResult> => {
    try {
      const response = await fetch(`${apiBaseUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        credentials: "include",
      });

      if (!response.ok) {
        let message = "Invalid username or password.";

        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload.detail) {
            message = payload.detail;
          }
        } catch {
          // Keep the fallback message when the response body is not JSON.
        }

        return { success: false, error: message };
      }

      const payload = (await response.json()) as LoginResponse;
      setAuthenticatedUsername(payload.username);
      setAuthReady(true);
      return { success: true };
    } catch {
      return { success: false, error: "Unable to reach authentication service." };
    }
  };

  const logout = async (): Promise<void> => {
    try {
      await fetch(`${apiBaseUrl}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Best-effort logout; clear local auth state regardless.
    }

    setAuthenticatedUsername(null);
    setAuthReady(true);
  };

  return {
    isAuthenticated,
    authenticatedUsername,
    authReady,
    login,
    logout,
  };
};
