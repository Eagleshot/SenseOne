import { createContext } from "react";

import { SensorData, TimezoneOption, Webcam } from "@/data/types";
import { ColorThemeKey } from "@/lib/appThemes";

export interface AppContextType {
  // Authentication
  isAuthenticated: boolean;
  authenticatedUsername: string | null;
  authReady: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;

  // Theme
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  colorTheme: ColorThemeKey;
  setColorTheme: (theme: ColorThemeKey) => void;
  brandLogoUrl: string | null;
  setBrandLogoUrl: (logoUrl: string | null) => void;

  // Timezone
  timezone: string;
  setTimezone: (tz: string) => void;
  timezones: TimezoneOption[];

  // Sidebar
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // Active webcam
  activeWebcam: Webcam;
  setActiveWebcam: (webcam: Webcam) => void;

  // Webcams
  webcamList: Webcam[];

  // Historical data
  historicalData: SensorData[];

  // Image timeline
  imageTimeline: { timestamp: Date; url: string }[];
  currentImageIndex: number;
  setCurrentImageIndex: (index: number) => void;
  refreshImageTimeline: () => Promise<void>;

  // Timelapse
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;

  // Camera schedule
  cameraStartTime: string;
  setCameraStartTime: (time: string) => void;
  cameraStopTime: string;
  setCameraStopTime: (time: string) => void;
  useSunriseSunset: boolean;
  setUseSunriseSunset: (value: boolean) => void;
  captureInterval: string;
  setCaptureInterval: (interval: string) => void;
  description: string;
  descriptionDraft: string;
  setDraftDescription: (description: string) => void;
  isDescriptionEditing: boolean;
  startDescriptionEdit: () => void;
  cancelDescriptionEdit: () => void;
  saveDescription: () => Promise<void>;
  isDescriptionSaving: boolean;
  descriptionError: string | null;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
  stationConfigError: string | null;
}

export const AppContext = createContext<AppContextType | undefined>(undefined);
