/* eslint-disable react-refresh/only-export-components */
import React, { createContext, ReactNode, useContext, useMemo, useState } from "react";

import { TIMEZONES } from "@/data/timezones";
import { apiBaseUrl } from "@/lib/apiClient";
import { resolveEffectiveTimezone, resolveStationTimezone } from "@/lib/stationTimezone";

import { AppPreferencesState, useAppPreferences } from "./useAppPreferences";
import { AuthSessionState, useAuthSession } from "./useAuthSession";
import { SidebarState, useSidebarState } from "./useSidebarState";
import { PlaybackState, StationDataState, useWebcamData } from "./useWebcamData";

// The app state is split into focused contexts so components re-render only
// for the slice they read. The split that matters most: image playback ticks
// `currentImageIndex` twice a second, which used to re-render every consumer
// of one merged context (sidebar, map, weather, …). Now only the hero image
// subscribes to playback.

type PreferencesValue = AppPreferencesState & {
  timezones: typeof TIMEZONES;
  /** What the user picked: an IANA zone or the "station" sentinel. The
   * `timezone` field always carries the resolved, effective IANA zone. */
  timezonePreference: string;
  /** The active station's local IANA zone (from its coordinates), or null. */
  stationTimezone: string | null;
};

type MapUiState = {
  /** Fullscreen map dialog, openable from outside the map (e.g. the sidebar).
   * Held as context state (not an event) so a request made before the
   * lazy-loaded map mounts still opens it. */
  isMapFullscreen: boolean;
  setMapFullscreen: (open: boolean) => void;
};

const AuthContext = createContext<AuthSessionState | undefined>(undefined);
const PreferencesContext = createContext<PreferencesValue | undefined>(undefined);
const SidebarContext = createContext<SidebarState | undefined>(undefined);
const MapUiContext = createContext<MapUiState | undefined>(undefined);
const StationDataContext = createContext<StationDataState | undefined>(undefined);
const PlaybackContext = createContext<PlaybackState | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const authSession = useAuthSession(apiBaseUrl);
  const appPreferences = useAppPreferences();
  const sidebarState = useSidebarState();
  const [isMapFullscreen, setMapFullscreen] = useState(false);
  const { station, playback } = useWebcamData(
    apiBaseUrl,
    authSession.isAuthenticated,
    authSession.authReady,
  );

  // "Station local" (the default) resolves to the active station's zone, so
  // every consumer of `timezone` — charts, tables, hero, weather — renders the
  // same clock without knowing about the sentinel.
  const { lat, lng } = station.activeWebcam.coordinates;
  const stationTimezone = useMemo(() => resolveStationTimezone(lat, lng), [lat, lng]);
  const preferencesValue = useMemo(
    () => ({
      ...appPreferences,
      timezone: resolveEffectiveTimezone(appPreferences.timezone, stationTimezone),
      timezonePreference: appPreferences.timezone,
      stationTimezone,
      timezones: TIMEZONES,
    }),
    [appPreferences, stationTimezone],
  );
  const mapUiValue = useMemo(() => ({ isMapFullscreen, setMapFullscreen }), [isMapFullscreen]);

  return (
    <AuthContext.Provider value={authSession}>
      <PreferencesContext.Provider value={preferencesValue}>
        <SidebarContext.Provider value={sidebarState}>
          <MapUiContext.Provider value={mapUiValue}>
            <StationDataContext.Provider value={station}>
              <PlaybackContext.Provider value={playback}>{children}</PlaybackContext.Provider>
            </StationDataContext.Provider>
          </MapUiContext.Provider>
        </SidebarContext.Provider>
      </PreferencesContext.Provider>
    </AuthContext.Provider>
  );
};

function useRequiredContext<T>(context: React.Context<T | undefined>, name: string): T {
  const value = useContext(context);
  if (!value) {
    throw new Error(`${name} must be used within an AppProvider`);
  }
  return value;
}

export const useAuth = () => useRequiredContext(AuthContext, "useAuth");
export const usePreferences = () => useRequiredContext(PreferencesContext, "usePreferences");
export const useSidebar = () => useRequiredContext(SidebarContext, "useSidebar");
export const useMapUi = () => useRequiredContext(MapUiContext, "useMapUi");
export const useStationData = () => useRequiredContext(StationDataContext, "useStationData");
export const usePlayback = () => useRequiredContext(PlaybackContext, "usePlayback");
