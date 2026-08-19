import { describe, expect, it } from "vitest";

import {
  createDefaultHistoryDateRange,
  DEFAULT_HISTORY_HOURS,
  filterHistoricalData,
  HISTORY_RANGE_PRESETS,
  historyTimeRangeForSelection,
  historyWindowHoursForLastHours,
  historyWindowHoursForRange,
  isMinuteWithinRange,
  MAX_HISTORY_HOURS,
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

  it("covers absolute ranges older than a week", () => {
    const from = new Date("2026-05-01T00:00:00");
    expect(historyWindowHoursForRange(from, now)).toBe(1000);
  });

  it("does not cap absolute ranges at the relative one-year maximum", () => {
    expect(historyWindowHoursForRange(new Date("2020-01-01T00:00:00"), now)).toBeGreaterThan(MAX_HISTORY_HOURS);
  });
});

describe("historyTimeRangeForSelection", () => {
  it("resolves a rolling relative range", () => {
    const now = new Date("2026-06-11T15:30:00Z");
    expect(
      historyTimeRangeForSelection({
        timeFrom: "00:00",
        timeTo: "23:59",
        timezone: "UTC",
        lastHours: 6,
        now,
      })
    ).toEqual([new Date("2026-06-11T09:30:00Z").getTime(), now.getTime()]);
  });

  it("resolves the inclusive absolute range in the selected timezone", () => {
    expect(
      historyTimeRangeForSelection({
        dateRange: { from: new Date(2026, 5, 10), to: new Date(2026, 5, 11) },
        timeFrom: "08:00",
        timeTo: "18:00",
        timezone: "Europe/Zurich",
      })
    ).toEqual([
      new Date("2026-06-10T06:00:00Z").getTime(),
      new Date("2026-06-11T16:00:59.999Z").getTime(),
    ]);
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

describe("last-hours presets", () => {
  const now = new Date("2026-06-11T15:30:00Z");

  it("keeps only rows within the rolling window", () => {
    const rows = [
      createRow("2026-06-11T15:00:00Z"), // 30 min ago
      createRow("2026-06-11T09:31:00Z"), // just inside 6h
      createRow("2026-06-11T09:29:00Z"), // just outside 6h
      createRow("2026-06-10T15:30:00Z"), // a day ago
    ];

    const result = filterHistoricalData({
      data: rows,
      timeFrom: "00:00",
      timeTo: "23:59",
      timezone: "UTC",
      lastHours: 6,
      now,
    });

    expect(result.map((row) => row.timestamp.toISOString())).toEqual([
      "2026-06-11T15:00:00.000Z",
      "2026-06-11T09:31:00.000Z",
    ]);
  });

  it("overrides the date and time filters while active", () => {
    const rows = [createRow("2026-06-11T15:00:00Z")];

    const result = filterHistoricalData({
      data: rows,
      // Day/time filters that would exclude the row if they applied.
      dateRange: { from: new Date(2026, 0, 1), to: new Date(2026, 0, 1) },
      timeFrom: "01:00",
      timeTo: "02:00",
      timezone: "UTC",
      lastHours: 1,
      now,
    });

    expect(result).toHaveLength(1);
  });

  it("clamps quick ranges between the default and the largest preset", () => {
    expect(historyWindowHoursForLastHours(1)).toBe(DEFAULT_HISTORY_HOURS);
    expect(historyWindowHoursForLastHours(24)).toBe(DEFAULT_HISTORY_HOURS);
    expect(historyWindowHoursForLastHours(168)).toBe(168);
    expect(historyWindowHoursForLastHours(1000)).toBe(1000);
    expect(historyWindowHoursForLastHours(10_000)).toBe(MAX_HISTORY_HOURS);
  });

  it("offers no preset beyond the largest relative range", () => {
    for (const preset of HISTORY_RANGE_PRESETS) {
      expect(preset.hours).toBeLessThanOrEqual(MAX_HISTORY_HOURS);
    }
  });
});
