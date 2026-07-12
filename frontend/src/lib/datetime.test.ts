import { describe, expect, it } from "vitest";

import { formatChartTickLabel, spansMultipleDays } from "@/lib/datetime";

describe("spansMultipleDays", () => {
  it("is false within one calendar day of the zone", () => {
    expect(
      spansMultipleDays(new Date("2026-06-11T01:00:00Z"), new Date("2026-06-11T22:00:00Z"), "UTC")
    ).toBe(false);
  });

  it("is true across a day boundary", () => {
    expect(
      spansMultipleDays(new Date("2026-06-10T23:00:00Z"), new Date("2026-06-11T01:00:00Z"), "UTC")
    ).toBe(true);
  });

  it("respects the timezone when deciding the boundary", () => {
    // 23:30 UTC and 00:30 UTC are different UTC days but the same day in Zurich (UTC+2).
    expect(
      spansMultipleDays(
        new Date("2026-06-10T23:30:00Z"),
        new Date("2026-06-11T00:30:00Z"),
        "Europe/Zurich"
      )
    ).toBe(false);
  });
});

describe("formatChartTickLabel", () => {
  const timestamp = new Date("2026-06-09T14:00:00Z");

  it("is time-only within a single day", () => {
    expect(formatChartTickLabel(timestamp, "UTC", false)).toBe("14:00");
  });

  it("includes the date on multi-day ranges", () => {
    expect(formatChartTickLabel(timestamp, "UTC", true)).toBe("Jun 9, 14:00");
  });
});
