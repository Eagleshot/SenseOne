import { describe, expect, it } from "vitest";

import { parseApiTimestamp, parseStationResponse, parseTimestampResponse, parseTimelineItemResponse } from "@/contexts/appContextUtils";

describe("appContextUtils timestamp parsing", () => {
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

  it("parses historical rows and timeline items with microsecond timestamps", () => {
    const historyRow = parseTimestampResponse({
      timestamp: "2026-04-21T20:06:51.864377Z",
      temperature: 5.1,
      humidity: 31,
      pressure: 1008,
      battery: 53,
      windSpeed: 17.1,
      windDirection: 299,
      visibility: 10.4,
      uvIndex: 0,
      dewPoint: 0.5,
      feelsLike: 3.6,
    });
    const timelineItem = parseTimelineItemResponse(
      {
        timestamp: "2026-04-21T20:06:51.864377Z",
        url: "/stations/station-1/images/example.png",
      },
      "/api"
    );

    expect(historyRow.timestamp.toISOString()).toBe("2026-04-21T20:06:51.864Z");
    expect(timelineItem.timestamp.toISOString()).toBe("2026-04-21T20:06:51.864Z");
  });
});
