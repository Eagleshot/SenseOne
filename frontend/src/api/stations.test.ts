import { describe, expect, it } from "vitest";

import { parseApiTimestamp, parseStationResponse, parseTimelineItemResponse } from "@/api/stations";

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

