import { describe, expect, it } from "vitest";

import {
  resolveEffectiveTimezone,
  resolveStationTimezone,
  STATION_LOCAL_TIMEZONE,
} from "@/lib/stationTimezone";

describe("resolveStationTimezone", () => {
  it("maps coordinates to their IANA zone", () => {
    expect(resolveStationTimezone(47.37, 8.54)).toBe("Europe/Zurich");
    expect(resolveStationTimezone(13.75, 100.5)).toBe("Asia/Bangkok");
  });

  it("returns null for the unset-coordinates placeholder and bad input", () => {
    expect(resolveStationTimezone(0, 0)).toBeNull();
    expect(resolveStationTimezone(999, 999)).toBeNull();
  });
});

describe("resolveEffectiveTimezone", () => {
  it("uses the station zone for the station-local preference", () => {
    expect(resolveEffectiveTimezone(STATION_LOCAL_TIMEZONE, "Asia/Bangkok")).toBe("Asia/Bangkok");
  });

  it("falls back to the browser zone when the station has none", () => {
    const browser = Intl.DateTimeFormat().resolvedOptions().timeZone;
    expect(resolveEffectiveTimezone(STATION_LOCAL_TIMEZONE, null)).toBe(browser);
  });

  it("an explicit preference always wins", () => {
    expect(resolveEffectiveTimezone("Europe/London", "Asia/Bangkok")).toBe("Europe/London");
  });
});
