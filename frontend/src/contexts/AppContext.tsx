import React, { ReactNode } from "react";

import { AppContext } from "./app-context";
import { useAppPreferences } from "./useAppPreferences";
import { useAuthSession } from "./useAuthSession";
import { useSidebarState } from "./useSidebarState";
import { useWebcamData } from "./useWebcamData";

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
  const authSession = useAuthSession(apiBaseUrl);
  const appPreferences = useAppPreferences();
  const sidebarState = useSidebarState();
  const webcamData = useWebcamData(apiBaseUrl, authSession.isAuthenticated);

  return (
    <AppContext.Provider
      value={{
        ...authSession,
        ...appPreferences,
        ...sidebarState,
        ...webcamData,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
