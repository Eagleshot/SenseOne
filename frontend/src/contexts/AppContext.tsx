import React, { ReactNode, createContext, useCallback, useContext, useEffect, useState } from "react";

import { SensorData, TimezoneOption, Webcam } from "@/data/types";
import { ColorThemeKey, applyColorTheme, isColorThemeKey } from "@/lib/appThemes";

type WebcamResponse = Omit<Webcam, "lastUpdate" | "nextUpdate"> & {
  lastUpdate: string;
  nextUpdate: string;
};
type SensorDataResponse = Omit<SensorData, "timestamp"> & { timestamp: string };
type TimelineItemResponse = { timestamp: string; url: string };
type LoginResponse = {
  expires_in: number;
  username: string;
};
type MeResponse = {
  username: string;
};
type TimelineImage = { timestamp: Date; url: string };
type FetchJsonOptions = RequestInit & {
  throwOnHttpError?: boolean;
};

interface AppContextType {
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
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const createFallbackWebcam = (): Webcam => ({
  id: "",
  name: "Loading...",
  location: "",
  coordinates: { lat: 0, lng: 0, altitude: 0 },
  thumbnail: "",
  currentImage: "",
  isOnline: false,
  lastUpdate: new Date(),
  nextUpdate: new Date(),
});

const isAbortError = (error: unknown): boolean =>
  error instanceof DOMException && error.name === "AbortError";

const parseWebcamResponse = (item: WebcamResponse): Webcam => ({
  ...item,
  lastUpdate: new Date(item.lastUpdate),
  nextUpdate: new Date(item.nextUpdate),
});

const parseSensorDataResponse = (row: SensorDataResponse): SensorData => ({
  ...row,
  timestamp: new Date(row.timestamp),
});

const parseTimelineItemResponse = (item: TimelineItemResponse): TimelineImage => ({
  ...item,
  timestamp: new Date(item.timestamp),
});

const fetchJson = async <T,>(url: string, options: FetchJsonOptions = {}): Promise<T | null> => {
  const { throwOnHttpError = true, ...requestInit } = options;
  const response = await fetch(url, requestInit);

  if (!response.ok) {
    if (throwOnHttpError) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return null;
  }

  return (await response.json()) as T;
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

  // Authentication (cookie-based session; no client-side token storage).
  const [authenticatedUsername, setAuthenticatedUsername] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const isAuthenticated = authReady && Boolean(authenticatedUsername);

  // Theme - check localStorage and system preference.
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const stored = localStorage.getItem("darkMode");
    if (stored !== null) return stored === "true";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  const [colorTheme, setColorThemeState] = useState<ColorThemeKey>(() => {
    const stored = localStorage.getItem("colorTheme");
    if (isColorThemeKey(stored)) return stored;
    return "embernova";
  });
  const [brandLogoUrl, setBrandLogoUrlState] = useState<string | null>(() => localStorage.getItem("brandLogoUrl"));

  // Timezone
  const [timezone, setTimezoneState] = useState(() => localStorage.getItem("timezone") || "Europe/Zurich");

  // Sidebar
  const [isSidebarOpen, setIsSidebarOpen] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth >= 1024 : true
  );

  // Webcams
  const [webcamList, setWebcamList] = useState<Webcam[]>([]);
  const [activeWebcam, setActiveWebcam] = useState<Webcam>(createFallbackWebcam);

  // Historical data
  const [historicalData, setHistoricalData] = useState<SensorData[]>([]);

  // Image timeline
  const [imageTimeline, setImageTimeline] = useState<TimelineImage[]>([]);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  // Timelapse
  const [isPlaying, setIsPlaying] = useState(false);

  // Camera schedule
  const [cameraStartTime, setCameraStartTimeState] = useState(() => localStorage.getItem("cameraStartTime") || "06:00");
  const [cameraStopTime, setCameraStopTimeState] = useState(() => localStorage.getItem("cameraStopTime") || "20:00");
  const [useSunriseSunset, setUseSunriseSunsetState] = useState(() => localStorage.getItem("useSunriseSunset") === "true");
  const [captureInterval, setCaptureIntervalState] = useState(() => localStorage.getItem("captureInterval") || "30");

  // Timezone options
  const [timezones, setTimezones] = useState<TimezoneOption[]>([]);

  useEffect(() => {
    // Remove legacy token-based state.
    localStorage.removeItem("authToken");
    localStorage.removeItem("authUsername");
  }, []);

  // Apply dark mode class to document
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDarkMode);
    localStorage.setItem("darkMode", String(isDarkMode));
  }, [isDarkMode]);

  // Save timezone
  useEffect(() => {
    localStorage.setItem("timezone", timezone);
  }, [timezone]);

  // Apply and save color theme
  useEffect(() => {
    applyColorTheme(colorTheme);
    localStorage.setItem("colorTheme", colorTheme);
  }, [colorTheme]);

  // Save brand logo URL
  useEffect(() => {
    if (brandLogoUrl) {
      localStorage.setItem("brandLogoUrl", brandLogoUrl);
      return;
    }
    localStorage.removeItem("brandLogoUrl");
  }, [brandLogoUrl]);

  // Save camera schedule settings
  useEffect(() => {
    localStorage.setItem("cameraStartTime", cameraStartTime);
    localStorage.setItem("cameraStopTime", cameraStopTime);
    localStorage.setItem("useSunriseSunset", String(useSunriseSunset));
    localStorage.setItem("captureInterval", captureInterval);
  }, [cameraStartTime, cameraStopTime, useSunriseSunset, captureInterval]);

  // Restore/validate auth session cookie.
  useEffect(() => {
    const validateSession = async () => {
      try {
        const payload = await fetchJson<MeResponse>(`${apiBaseUrl}/auth/me`, {
          credentials: "include",
          throwOnHttpError: false,
        });
        if (!payload) {
          setAuthenticatedUsername(null);
          return;
        }
        setAuthenticatedUsername(payload.username);
      } catch {
        setAuthenticatedUsername(null);
      } finally {
        setAuthReady(true);
      }
    };

    void validateSession();
  }, [apiBaseUrl]);

  // Load webcams (public) and timezones (public).
  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    const fetchWebcams = async () => {
      try {
        const data = await fetchJson<WebcamResponse[]>(`${apiBaseUrl}/webcams`, {
          signal: controller.signal,
        });
        if (!data) return;
        if (!isMounted) return;

        const parsed = data.map(parseWebcamResponse);
        setWebcamList(parsed);
        if (parsed.length > 0) {
          setActiveWebcam((prev) => parsed.find((cam) => cam.id === prev.id) ?? parsed[0]);
        } else {
          setActiveWebcam(createFallbackWebcam());
        }
      } catch (err) {
        if (isAbortError(err)) return;
      }
    };

    const fetchTimezones = async () => {
      try {
        const data = await fetchJson<TimezoneOption[]>(`${apiBaseUrl}/timezones`, { signal: controller.signal });
        if (!data) return;
        if (!isMounted) return;
        setTimezones(data);
      } catch (err) {
        if (isAbortError(err)) return;
      }
    };

    void fetchWebcams();
    void fetchTimezones();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [apiBaseUrl]);

  const fetchImageTimelineData = useCallback(async (options: { signal?: AbortSignal } = {}) => {
    if (!activeWebcam.id) return;
    const historyUrl = `${apiBaseUrl}/history?hours=24&webcam_id=${encodeURIComponent(activeWebcam.id)}`;
    const timelineUrl = `${apiBaseUrl}/timeline?count=48&webcam_id=${encodeURIComponent(activeWebcam.id)}`;
    const { signal } = options;

    try {
      const [historyData, timelineData] = await Promise.all([
        fetchJson<SensorDataResponse[]>(historyUrl, { signal, throwOnHttpError: false }),
        fetchJson<TimelineItemResponse[]>(timelineUrl, { signal, throwOnHttpError: false }),
      ]);

      if (historyData) {
        setHistoricalData(historyData.map(parseSensorDataResponse));
      } else {
        setHistoricalData([]);
      }

      if (timelineData) {
        const parsedTimeline = timelineData.map(parseTimelineItemResponse);
        setImageTimeline(parsedTimeline);
        setCurrentImageIndex(Math.max(parsedTimeline.length - 1, 0));
        setIsPlaying(false);
      } else {
        setImageTimeline([]);
        setCurrentImageIndex(0);
        setIsPlaying(false);
      }
    } catch (err) {
      if (isAbortError(err)) return;
      setHistoricalData([]);
      setImageTimeline([]);
      setCurrentImageIndex(0);
      setIsPlaying(false);
    }
  }, [apiBaseUrl, activeWebcam.id]);

  useEffect(() => {
    if (!activeWebcam.id) return;

    const controller = new AbortController();
    void fetchImageTimelineData({ signal: controller.signal });

    return () => {
      controller.abort();
    };
  }, [activeWebcam.id, apiBaseUrl, fetchImageTimelineData]);

  const refreshImageTimeline = async () => {
    await fetchImageTimelineData();
  };

  // Update document title/meta with active webcam name.
  useEffect(() => {
    const title = `${activeWebcam.name} | Eagleshot`;
    document.title = title;
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) ogTitle.setAttribute("content", title);
    const twitterSite = document.querySelector('meta[name="twitter:site"]');
    if (twitterSite) twitterSite.setAttribute("content", title);
  }, [activeWebcam.name]);

  // Timelapse auto-advance.
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentImageIndex((prev) => {
        if (prev >= imageTimeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 500);

    return () => clearInterval(interval);
  }, [isPlaying, imageTimeline.length]);

  // Keep sidebar behavior aligned with desktop/mobile breakpoints.
  useEffect(() => {
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    const syncSidebarState = (event?: MediaQueryListEvent) => {
      setIsSidebarOpen(event ? event.matches : desktopQuery.matches);
    };

    syncSidebarState();
    desktopQuery.addEventListener("change", syncSidebarState);
    return () => desktopQuery.removeEventListener("change", syncSidebarState);
  }, []);

  const toggleDarkMode = () => setIsDarkMode((prev) => !prev);
  const toggleSidebar = () => setIsSidebarOpen((prev) => !prev);

  const login = async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
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
          if (payload.detail) message = payload.detail;
        } catch {
          // Keep fallback message when no JSON payload is available.
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

  return (
    <AppContext.Provider
      value={{
        isAuthenticated,
        authenticatedUsername,
        authReady,
        login,
        logout,
        isDarkMode,
        toggleDarkMode,
        colorTheme,
        setColorTheme: setColorThemeState,
        brandLogoUrl,
        setBrandLogoUrl: setBrandLogoUrlState,
        timezone,
        setTimezone: setTimezoneState,
        timezones,
        isSidebarOpen,
        toggleSidebar,
        setSidebarOpen: setIsSidebarOpen,
        activeWebcam,
        setActiveWebcam,
        webcamList,
        historicalData,
        imageTimeline,
        currentImageIndex,
        setCurrentImageIndex,
        refreshImageTimeline,
        isPlaying,
        setIsPlaying,
        cameraStartTime,
        setCameraStartTime: setCameraStartTimeState,
        cameraStopTime,
        setCameraStopTime: setCameraStopTimeState,
        useSunriseSunset,
        setUseSunriseSunset: setUseSunriseSunsetState,
        captureInterval,
        setCaptureInterval: setCaptureIntervalState,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
