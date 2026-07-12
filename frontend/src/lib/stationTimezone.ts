import tzLookup from "tz-lookup";

/** Sentinel timezone preference: render timestamps in the active station's
 * local timezone (derived from its coordinates). This is the default — for a
 * webcam site, "what time was it THERE" is usually the question. */
export const STATION_LOCAL_TIMEZONE = "station";

/** IANA timezone at the station's coordinates, or null when the station has
 * no usable position ((0,0) is the "not configured" placeholder). */
export const resolveStationTimezone = (lat: number, lng: number): string | null => {
  if (lat === 0 && lng === 0) return null;
  try {
    return tzLookup(lat, lng);
  } catch {
    return null; // out-of-range coordinates
  }
};

const browserTimezone = (): string => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

/** The IANA timezone all timestamps render in: the explicit preference when
 * one is set, else the station's local zone, else the browser's. */
export const resolveEffectiveTimezone = (
  preference: string,
  stationTimezone: string | null,
): string => {
  if (preference !== STATION_LOCAL_TIMEZONE) return preference;
  return stationTimezone ?? browserTimezone();
};
