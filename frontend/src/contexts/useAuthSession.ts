import { useEffect, useState } from "react";

import { getCurrentUser, loginUser, logoutUser, type AuthResult } from "@/api/auth";
import { isAbortError } from "@/lib/apiClient";

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
    const controller = new AbortController();

    const validateSession = async () => {
      try {
        const payload = await getCurrentUser(apiBaseUrl, controller.signal);

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
    const result = await loginUser(apiBaseUrl, username, password);
    if (result.success && result.username) {
      setAuthenticatedUsername(result.username);
      setAuthReady(true);
    }
    return result.success ? { success: true } : { success: false, error: result.error };
  };

  const logout = async (): Promise<void> => {
    try {
      await logoutUser(apiBaseUrl);
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

