import { describe, expect, it } from "vitest";

import {
  buildSensorCsv,
  createFormattedTimestampMap,
  filterAndSortSensorRows,
  paginateRows,
} from "./rawDataTableUtils";
import type { SensorData } from "@/data/types";

const row = (timestamp: string, temperature: number, battery: number): SensorData => ({
  timestamp: new Date(timestamp),
  temperature,
  humidity: 50,
  pressure: 1010,
  battery,
  windSpeed: 5,
  windDirection: 180,
  visibility: 10,
  uvIndex: 2,
  dewPoint: 3,
  feelsLike: temperature,
});

describe("rawDataTableUtils", () => {
  const rows = [
    row("2026-01-01T10:00:00Z", 4, 80),
    row("2026-01-01T11:00:00Z", 8, 30),
  ];

  it("filters and sorts sensor rows", () => {
    const formattedTimestamps = createFormattedTimestampMap(rows, "UTC");
    const result = filterAndSortSensorRows({
      data: rows,
      formattedTimestamps,
      searchQuery: "30",
      sortField: "temperature",
      sortDirection: "desc",
    });

    expect(result).toEqual([rows[1]]);
  });

  it("paginates and builds csv output", () => {
    expect(paginateRows(rows, 2, 1)).toEqual([rows[1]]);
    expect(buildSensorCsv(rows, "UTC")).toContain("Temperature");
    expect(buildSensorCsv(rows, "UTC")).toContain("2026");
  });
});

