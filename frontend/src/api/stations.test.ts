import { describe, expect, it } from "vitest";

import {
  FALLBACK_WEBCAM,
  NOT_FOUND_WEBCAM,
  parseApiTimestamp,
  parseStationResponse,
  parseTimelineItemResponse,
  resolveStationSelection,
  UNAVAILABLE_WEBCAM,
} from "@/api/stations";
import type { Webcam } from "@/data/types";

describe("station API parsing", () => {
  it("normalizes microsecond ISO timestamps to valid Date objects", () => {
    const parsed = parseApiTimestamp("2026-04-21T20:06:51.864377Z");

    expect(parsed.toISOString()).toBe("2026-04-21T20:06:51.864Z");
  });

  it("parses station update timestamps written by the mock seeder", () => {
    const parsed = parseStationResponse({
      id: "station-1",
      name: "Station 1",
      location: "Somewhere",
      coordinates: { lat: 0, lng: 0, altitude: 0 },
      lastUpdate: "2026-04-21T20:06:51.864377Z",
      nextUpdate: "2026-04-21T21:06:51.123456Z",
    });

    expect(parsed.lastUpdate?.toISOString()).toBe("2026-04-21T20:06:51.864Z");
    expect(parsed.nextUpdate?.toISOString()).toBe("2026-04-21T21:06:51.123Z");
  });

  it("parses timeline items with microsecond timestamps", () => {
    const timelineItem = parseTimelineItemResponse(
      {
        timestamp: "2026-04-21T20:06:51.864377Z",
        url: "/stations/station-1/images/example.png",
      },
      "/api"
    );

    expect(timelineItem.timestamp.toISOString()).toBe("2026-04-21T20:06:51.864Z");
    expect(timelineItem.url).toBe("/api/stations/station-1/images/example.png");
  });
});

describe("resolveStationSelection", () => {
  const station = (id: string, urlSlug?: string): Webcam => ({
    ...FALLBACK_WEBCAM,
    id,
    urlSlug,
    name: `Station ${id}`,
  });
  const list = [station("aaa111", "alpha-cam"), station("bbb222", "beta-cam")];

  it("matches the URL token against the stable id", () => {
    const current = { ...FALLBACK_WEBCAM, id: "bbb222" };
    expect(resolveStationSelection(list, current, true)).toBe(list[1]);
  });

  it("matches the URL token against the editable url slug", () => {
    const current = { ...FALLBACK_WEBCAM, id: "alpha-cam" };
    expect(resolveStationSelection(list, current, true)).toBe(list[0]);
  });

  it("defaults to the first station when no token is set", () => {
    expect(resolveStationSelection(list, FALLBACK_WEBCAM, true)).toBe(list[0]);
  });

  it("resolves an unknown token to the not-found state, keeping the token", () => {
    const current = { ...FALLBACK_WEBCAM, id: "ghost-cam" };
    const resolved = resolveStationSelection(list, current, true);
    expect(resolved.name).toBe(NOT_FOUND_WEBCAM.name);
    expect(resolved.id).toBe("ghost-cam"); // a later sign-in can still resolve it
  });

  it("leaves an unknown token unresolved while auth is still settling", () => {
    const current = { ...FALLBACK_WEBCAM, id: "ghost-cam" };
    expect(resolveStationSelection(list, current, false)).toBe(current);
  });

  it("keeps the token through the empty-list unavailable state", () => {
    const current = { ...FALLBACK_WEBCAM, id: "ghost-cam" };
    const resolved = resolveStationSelection([], current, true);
    expect(resolved.name).toBe(UNAVAILABLE_WEBCAM.name);
    expect(resolved.id).toBe("ghost-cam");
  });
});

