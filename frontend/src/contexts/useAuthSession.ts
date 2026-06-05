import { useCallback, useEffect, useMemo, useState } from "react";

import { getCurrentUser, loginUser, logoutUser, type AuthResult } from "@/api/auth";
import { isAbortError } from "@/lib/apiClient";

export type AuthSessionState = {
  isAuthenticated: boolean;
  authenticatedEmail: string | null;
  authReady: boolean;
  login: (email: string, password: string) => Promise<AuthResult>;
  logout: () => Promise<void>;
};

export const useAuthSession = (apiBaseUrl: string): AuthSessionState => {
  const [authenticatedEmail, setAuthenticatedEmail] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const isAuthenticated = authReady && Boolean(authenticatedEmail);

  useEffect(() => {
    const controller = new AbortController();

    const validateSession = async () => {
      try {
        const payload = await getCurrentUser(apiBaseUrl, controller.signal);

        if (controller.signal.aborted) return;
        setAuthenticatedEmail(payload?.email ?? null);
      } catch (error) {
        if (isAbortError(error)) return;
        setAuthenticatedEmail(null);
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

  const login = useCallback(async (email: string, password: string): Promise<AuthResult> => {
    const result = await loginUser(apiBaseUrl, email, password);
    if (result.success && result.email) {
      setAuthenticatedEmail(result.email);
      setAuthReady(true);
    }
    return result.success ? { success: true } : { success: false, error: result.error };
  }, [apiBaseUrl]);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutUser(apiBaseUrl);
    } catch {
      // Best-effort logout; clear local auth state regardless.
    }

    setAuthenticatedEmail(null);
    setAuthReady(true);
  }, [apiBaseUrl]);

  return useMemo(() => ({
    isAuthenticated,
    authenticatedEmail,
    authReady,
    login,
    logout,
  }), [authReady, authenticatedEmail, isAuthenticated, login, logout]);
};

