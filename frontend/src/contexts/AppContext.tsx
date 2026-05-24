/* eslint-disable react-refresh/only-export-components */
import React, { createContext, ReactNode, useContext, useMemo } from "react";

import { TIMEZONES } from "@/data/timezones";
import { SensorData, Webcam } from "@/data/types";
import { apiBaseUrl } from "@/lib/apiClient";
import { ColorThemeKey } from "@/lib/appThemes";

import { MapStyleKey, useAppPreferences } from "./useAppPreferences";
import { useAuthSession } from "./useAuthSession";
import { useSidebarState } from "./useSidebarState";
import { StationScheduleConfig } from "@/api/stations";
import { useWebcamData } from "./useWebcamData";

interface AppProviderProps {
  children: ReactNode;
}

export interface AppContextType {
  isAuthenticated: boolean;
  authenticatedUsername: string | null;
  authReady: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;

  isDarkMode: boolean;
  toggleDarkMode: () => void;
  colorTheme: ColorThemeKey;
  setColorTheme: (theme: ColorThemeKey) => void;
  brandLogoUrl: string | null;
  setBrandLogoUrl: (logoUrl: string | null) => void;
  mapStyle: MapStyleKey;
  setMapStyle: (style: MapStyleKey) => void;

  timezone: string;
  setTimezone: (tz: string) => void;
  timezones: typeof TIMEZONES;

  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  activeWebcam: Webcam;
  setActiveWebcam: (webcam: Webcam) => void;
  webcamList: Webcam[];
  historicalData: SensorData[];
  imageTimeline: { timestamp: Date; url: string }[];
  currentImageIndex: number;
  setCurrentImageIndex: (index: number) => void;
  refreshImageTimeline: () => Promise<void>;

  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;

  stationStartTime: string;
  stationStopTime: string;
  useSunriseSunset: boolean;
  captureInterval: string;
  saveStationSchedule: (schedule: StationScheduleConfig) => Promise<void>;
  description: string;
  descriptionDraft: string;
  setDraftDescription: (description: string) => void;
  saveDescription: () => Promise<boolean>;
  isDescriptionSaving: boolean;
  descriptionError: string | null;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
  stationConfigError: string | null;

  isPublic: boolean;
  setIsPublic: (isPublic: boolean) => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const authSession = useAuthSession(apiBaseUrl);
  const appPreferences = useAppPreferences();
  const sidebarState = useSidebarState();
  const webcamData = useWebcamData(apiBaseUrl, authSession.isAuthenticated);
  const value = useMemo(
    () => ({
      ...authSession,
      ...appPreferences,
      ...sidebarState,
      ...webcamData,
    }),
    [appPreferences, authSession, sidebarState, webcamData]
  );

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }

  return context;
};

