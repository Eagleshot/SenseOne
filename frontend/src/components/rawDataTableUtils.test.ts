import { describe, expect, it } from "vitest";

import {
  buildSensorCsv,
  collectMetricKeys,
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
  reception: 70,
});

describe("rawDataTableUtils", () => {
  const rows = [
    row("2026-01-01T10:00:00Z", 4, 80),
    row("2026-01-01T11:00:00Z", 8, 30),
  ];
  const columns = collectMetricKeys(rows);

  it("derives display columns from the metrics present", () => {
    expect(columns).toEqual(["temperature", "humidity", "pressure", "battery", "reception"]);
  });

  it("filters and sorts sensor rows", () => {
    const formattedTimestamps = createFormattedTimestampMap(rows, "UTC");
    const result = filterAndSortSensorRows({
      data: rows,
      formattedTimestamps,
      searchQuery: "30",
      sortField: "temperature",
      sortDirection: "desc",
      columns,
    });

    expect(result).toEqual([rows[1]]);
  });

  it("paginates and builds csv output", () => {
    expect(paginateRows(rows, 2, 1)).toEqual([rows[1]]);
    expect(buildSensorCsv(rows, "UTC", columns)).toContain("Temperature");
    expect(buildSensorCsv(rows, "UTC", columns)).toContain("2026");
  });
});
