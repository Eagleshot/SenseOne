import { useCallback, useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { ColorThemeKey, applyColorTheme, isColorThemeKey } from "@/lib/appThemes";
import { STATION_LOCAL_TIMEZONE } from "@/lib/stationTimezone";
import { getStoredOptionalString, setStoredOptionalString } from "@/lib/storage";

export type MapStyleKey = "abstract" | "satellite";

const isMapStyleKey = (value: string | null): value is MapStyleKey => value === "abstract" || value === "satellite";

export type AppPreferencesState = {
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
};

// Read-on-init + write-on-change for one localStorage-backed preference. `parse`
// turns the stored string into T (or undefined to fall back to `init()`). Values
// serialize uniformly: null clears the key, everything else via String(). Side
// effects beyond persistence (DOM class, theme) stay as separate effects in the caller.
function usePersistedState<T extends string | boolean | null>(
  key: string,
  init: () => T,
  parse: (raw: string) => T | undefined,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    const raw = getStoredOptionalString(key);
    const parsed = raw !== null ? parse(raw) : undefined;
    return parsed !== undefined ? parsed : init();
  });

  useEffect(() => {
    setStoredOptionalString(key, value === null ? null : String(value));
  }, [key, value]);

  return [value, setValue];
}

const prefersDark = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;

export const useAppPreferences = (): AppPreferencesState => {
  const [isDarkMode, setIsDarkMode] = usePersistedState<boolean>(
    "darkMode", prefersDark, (raw) => raw === "true",
  );
  const [colorTheme, setColorTheme] = usePersistedState<ColorThemeKey>(
    "colorTheme", () => "embernova", (raw) => (isColorThemeKey(raw) ? raw : undefined),
  );
  const [brandLogoUrl, setBrandLogoUrl] = usePersistedState<string | null>(
    "brandLogoUrl", () => null, (raw) => raw,
  );
  const [mapStyle, setMapStyle] = usePersistedState<MapStyleKey>(
    "mapStyle", () => "abstract", (raw) => (isMapStyleKey(raw) ? raw : undefined),
  );
  // The stored value is a *preference*: an explicit IANA zone, or the
  // "station" sentinel (default) meaning "the active station's local time".
  // AppContext resolves it to the effective IANA zone per station.
  const [timezone, setTimezone] = usePersistedState<string>(
    "timezone", () => STATION_LOCAL_TIMEZONE, (raw) => raw,
  );

  // Side effects beyond persistence (usePersistedState already writes each to storage).
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDarkMode);
  }, [isDarkMode]);
  useEffect(() => {
    applyColorTheme(colorTheme);
  }, [colorTheme]);

  const toggleDarkMode = useCallback(() => setIsDarkMode((current) => !current), [setIsDarkMode]);

  return useMemo(() => ({
    isDarkMode,
    toggleDarkMode,
    colorTheme,
    setColorTheme,
    brandLogoUrl,
    setBrandLogoUrl,
    mapStyle,
    setMapStyle,
    timezone,
    setTimezone,
  }), [
    brandLogoUrl,
    colorTheme,
    isDarkMode,
    mapStyle,
    setBrandLogoUrl,
    setColorTheme,
    setMapStyle,
    setTimezone,
    timezone,
    toggleDarkMode,
  ]);
};

