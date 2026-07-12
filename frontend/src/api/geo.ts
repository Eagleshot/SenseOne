import { apiBaseUrl, fetchJson } from "@/lib/apiClient";

export type ReverseGeocodeResult = {
  name: string | null;
  countryCode: string | null; // ISO 3166-1 alpha-2 (e.g. "CH")
  state: string | null;
};

/** Nearest place for a coordinate, via the backend's OpenWeather geocoding
 * proxy (signed-in users only). Returns null on any error — callers treat the
 * lookup as best-effort. */
export const reverseGeocode = (lat: number, lon: number, signal?: AbortSignal) =>
  fetchJson<ReverseGeocodeResult>(
    `${apiBaseUrl}/geo/reverse?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`,
    { credentials: "include", signal, throwOnHttpError: false },
  );
