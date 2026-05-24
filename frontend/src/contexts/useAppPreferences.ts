import { useCallback, useEffect, useMemo, useState } from "react";

import { ColorThemeKey, applyColorTheme, isColorThemeKey } from "@/lib/appThemes";
import {
  getStoredOptionalString,
  getStoredString,
  setStoredBoolean,
  setStoredOptionalString,
  setStoredString,
} from "@/lib/storage";

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

const getInitialDarkMode = () => {
  const storedValue = getStoredOptionalString("darkMode");
  if (storedValue !== null) {
    return storedValue === "true";
  }

  return typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)").matches : false;
};

export const useAppPreferences = (): AppPreferencesState => {
  const [isDarkMode, setIsDarkMode] = useState(getInitialDarkMode);
  const [colorTheme, setColorThemeState] = useState<ColorThemeKey>(() => {
    const storedTheme = getStoredOptionalString("colorTheme");
    return isColorThemeKey(storedTheme) ? storedTheme : "embernova";
  });
  const [brandLogoUrl, setBrandLogoUrlState] = useState<string | null>(() => getStoredOptionalString("brandLogoUrl"));
  const [mapStyle, setMapStyleState] = useState<MapStyleKey>(() => {
    const storedStyle = getStoredOptionalString("mapStyle");
    if (isMapStyleKey(storedStyle)) {
      return storedStyle;
    }
    // Migrate legacy keys (smoothBright/smoothDark â†’ abstract) and persist
    // the migrated value so we don't repeat this on every load.
    if (storedStyle === "smoothBright" || storedStyle === "smoothDark") {
      setStoredString("mapStyle", "abstract");
    }
    return "abstract";
  });
  const [timezone, setTimezoneState] = useState(() => getStoredString("timezone", "Europe/Zurich"));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDarkMode);
    setStoredBoolean("darkMode", isDarkMode);
  }, [isDarkMode]);

  useEffect(() => {
    setStoredString("timezone", timezone);
  }, [timezone]);

  useEffect(() => {
    applyColorTheme(colorTheme);
    setStoredString("colorTheme", colorTheme);
  }, [colorTheme]);

  useEffect(() => {
    setStoredOptionalString("brandLogoUrl", brandLogoUrl);
  }, [brandLogoUrl]);

  useEffect(() => {
    setStoredString("mapStyle", mapStyle);
  }, [mapStyle]);

  const toggleDarkMode = useCallback(() => setIsDarkMode((currentValue) => !currentValue), []);
  const setColorTheme = useCallback((theme: ColorThemeKey) => setColorThemeState(theme), []);
  const setBrandLogoUrl = useCallback((logoUrl: string | null) => setBrandLogoUrlState(logoUrl), []);
  const setMapStyle = useCallback((style: MapStyleKey) => setMapStyleState(style), []);
  const setTimezone = useCallback((tz: string) => setTimezoneState(tz), []);

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

