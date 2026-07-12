import { describe, expect, it } from "vitest";

import {
  createDefaultHistoryDateRange,
  DEFAULT_HISTORY_HOURS,
  filterHistoricalData,
  historyWindowHoursForRange,
  isMinuteWithinRange,
  MAX_HISTORY_HOURS,
  minSelectableHistoryDate,
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

describe("historyWindowHoursForRange", () => {
  const now = new Date("2026-06-11T15:30:00");

  it("defaults when no range start is picked", () => {
    expect(historyWindowHoursForRange(undefined, now)).toBe(DEFAULT_HISTORY_HOURS);
  });

  it("covers back to the start of the picked first day", () => {
    // 3 days ago at local midnight -> 3*24h + the 15.5h elapsed today, ceiled.
    const from = new Date("2026-06-08T10:00:00");
    expect(historyWindowHoursForRange(from, now)).toBe(88);
  });

  it("never shrinks below the default window", () => {
    const from = new Date("2026-06-11T01:00:00"); // today: only ~16h needed
    expect(historyWindowHoursForRange(from, now)).toBe(DEFAULT_HISTORY_HOURS);
  });

  it("clamps to the backend's 7-day cap", () => {
    const from = new Date("2026-05-01T00:00:00");
    expect(historyWindowHoursForRange(from, now)).toBe(MAX_HISTORY_HOURS);
  });
});

describe("minSelectableHistoryDate", () => {
  it("is the start of the earliest day the max lookback reaches", () => {
    const now = new Date("2026-06-11T15:30:00");
    const earliest = minSelectableHistoryDate(now);
    expect(earliest.getHours()).toBe(0);
    expect(earliest.getMinutes()).toBe(0);
    // 168h before Jun 11 15:30 is Jun 4 15:30 -> floored to Jun 4 00:00 local.
    expect(earliest.getDate()).toBe(4);
    expect(earliest.getMonth()).toBe(5);
  });
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
        from: new Date(2026, 2, 10),
        to: new Date(2026, 2, 10),
      },
      timeFrom: "07:00",
      timeTo: "12:00",
      timezone: "UTC",
    });

    expect(result).toHaveLength(1);
    expect(result[0]?.timestamp.toISOString()).toBe(rows[0]?.timestamp.toISOString());
  });

  it("filters rows against the selected timezone instead of the browser timezone", () => {
    const rows = [
      createRow("2026-01-02T05:30:00Z"),
      createRow("2026-01-03T08:30:00Z"),
    ];
    const dateRange = {
      from: new Date(2026, 0, 2),
      to: new Date(2026, 0, 2),
    };

    const utcResult = filterHistoricalData({
      data: rows,
      dateRange,
      timeFrom: "00:00",
      timeTo: "23:59",
      timezone: "UTC",
    });
    const honoluluResult = filterHistoricalData({
      data: rows,
      dateRange,
      timeFrom: "00:00",
      timeTo: "23:59",
      timezone: "Pacific/Honolulu",
    });

    expect(utcResult.map((row) => row.timestamp.toISOString())).toEqual(["2026-01-02T05:30:00.000Z"]);
    expect(honoluluResult.map((row) => row.timestamp.toISOString())).toEqual(["2026-01-03T08:30:00.000Z"]);
  });

  it("keeps the clicked calendar day stable when app timezone differs from the machine timezone", () => {
    const rows = [createRow("2026-01-03T03:00:00Z")];

    const result = filterHistoricalData({
      data: rows,
      dateRange: {
        from: new Date(2026, 0, 2),
        to: new Date(2026, 0, 2),
      },
      timeFrom: "00:00",
      timeTo: "23:59",
      timezone: "Pacific/Honolulu",
    });

    expect(result).toHaveLength(1);
    expect(result[0]?.timestamp.toISOString()).toBe("2026-01-03T03:00:00.000Z");
  });

  it("applies overnight time windows in the selected timezone", () => {
    const rows = [
      createRow("2026-01-02T08:00:00Z"),
      createRow("2026-01-02T16:00:00Z"),
      createRow("2026-01-02T22:00:00Z"),
    ];

    const result = filterHistoricalData({
      data: rows,
      timeFrom: "22:00",
      timeTo: "06:00",
      timezone: "Pacific/Honolulu",
    });

    expect(result.map((row) => row.timestamp.toISOString())).toEqual([
      "2026-01-02T08:00:00.000Z",
      "2026-01-02T16:00:00.000Z",
    ]);
  });

  it("creates a default range covering roughly the last day", () => {
    const range = createDefaultHistoryDateRange();

    expect(range.from).toBeInstanceOf(Date);
    expect(range.to).toBeInstanceOf(Date);
    expect((range.to?.getTime() ?? 0) - (range.from?.getTime() ?? 0)).toBeGreaterThanOrEqual(23 * 60 * 60 * 1000);
  });
});

