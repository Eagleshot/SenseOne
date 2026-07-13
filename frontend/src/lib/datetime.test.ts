import { describe, expect, it } from "vitest";

import { formatChartTickLabel, formatCountdown, spansMultipleDays } from "@/lib/datetime";

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

describe("formatCountdown", () => {
  const now = new Date("2026-06-11T12:00:00Z");
  const inSeconds = (s: number) => new Date(now.getTime() + s * 1000);
  const inMinutes = (m: number) => new Date(now.getTime() + m * 60000);

  it("says 'less than a min.' under 30 seconds", () => {
    expect(formatCountdown(inSeconds(20), now)).toBe("in less than a min.");
  });

  it("shows whole minutes under an hour", () => {
    expect(formatCountdown(inMinutes(1), now)).toBe("in 1 min.");
    expect(formatCountdown(inMinutes(45), now)).toBe("in 45 min.");
    expect(formatCountdown(inMinutes(59), now)).toBe("in 59 min.");
  });

  it("drops the minutes when exactly on the hour", () => {
    expect(formatCountdown(inMinutes(60), now)).toBe("in 1 h");
    expect(formatCountdown(inMinutes(120), now)).toBe("in 2 h");
  });

  it("shows hours and minutes past the hour", () => {
    expect(formatCountdown(inMinutes(65), now)).toBe("in 1 h 5 min.");
    expect(formatCountdown(inMinutes(150), now)).toBe("in 2 h 30 min.");
  });
});
