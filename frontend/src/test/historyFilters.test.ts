import { describe, expect, it } from "vitest";

import {
  createDefaultHistoryDateRange,
  filterHistoricalData,
  isMinuteWithinRange,
  parseTimeToMinutes,
} from "@/lib/historyFilters";

const createRow = (isoTimestamp: string) => ({
  timestamp: new Date(isoTimestamp),
  temperature: 0,
  humidity: 0,
  pressure: 0,
  battery: 0,
  windSpeed: 0,
  windDirection: 0,
  visibility: 0,
  uvIndex: 0,
  dewPoint: 0,
  feelsLike: 0,
});

describe("historyFilters", () => {
  it("parses valid times into minutes", () => {
    expect(parseTimeToMinutes("00:00")).toBe(0);
    expect(parseTimeToMinutes("13:45")).toBe(825);
  });

  it("rejects invalid times", () => {
    expect(parseTimeToMinutes("hello")).toBeUndefined();
    expect(parseTimeToMinutes("12:nope")).toBeUndefined();
  });

  it("supports overnight time windows", () => {
    expect(isMinuteWithinRange(23 * 60, 22 * 60, 6 * 60)).toBe(true);
    expect(isMinuteWithinRange(5 * 60, 22 * 60, 6 * 60)).toBe(true);
    expect(isMinuteWithinRange(12 * 60, 22 * 60, 6 * 60)).toBe(false);
  });

  it("filters rows by date and time range", () => {
    const rows = [
      createRow("2026-03-10T08:00:00"),
      createRow("2026-03-10T15:00:00"),
      createRow("2026-03-11T09:30:00"),
    ];

    const result = filterHistoricalData({
      data: rows,
      dateRange: {
        from: new Date("2026-03-10T00:00:00"),
        to: new Date("2026-03-10T23:59:59"),
      },
      timeFrom: "07:00",
      timeTo: "12:00",
    });

    expect(result).toHaveLength(1);
    expect(result[0]?.timestamp.toISOString()).toBe(rows[0]?.timestamp.toISOString());
  });

  it("creates a default range covering roughly the last day", () => {
    const range = createDefaultHistoryDateRange();

    expect(range.from).toBeInstanceOf(Date);
    expect(range.to).toBeInstanceOf(Date);
    expect((range.to?.getTime() ?? 0) - (range.from?.getTime() ?? 0)).toBeGreaterThanOrEqual(23 * 60 * 60 * 1000);
  });
});
