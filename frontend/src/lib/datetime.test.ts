import { describe, expect, it } from "vitest";

import {
  formatChartTickLabel,
  formatCountdown,
  spansMultipleDays,
  utcTimeOfDayToZoned,
  zonedTimeOfDayToUtc,
} from "@/lib/datetime";

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

describe("schedule time-of-day conversion", () => {
  const summer = new Date("2026-07-22T10:00:00Z"); // Zurich at UTC+2 (CEST)
  const winter = new Date("2026-01-22T10:00:00Z"); // Zurich at UTC+1 (CET)

  it("converts UTC to the zone's wall clock", () => {
    expect(utcTimeOfDayToZoned("06:00", "Europe/Zurich", summer)).toBe("08:00");
    expect(utcTimeOfDayToZoned("06:00", "Europe/Zurich", winter)).toBe("07:00");
    expect(utcTimeOfDayToZoned("06:30", "UTC", summer)).toBe("06:30");
  });

  it("converts the zone's wall clock to UTC", () => {
    expect(zonedTimeOfDayToUtc("08:00", "Europe/Zurich", summer)).toBe("06:00");
    expect(zonedTimeOfDayToUtc("07:00", "Europe/Zurich", winter)).toBe("06:00");
    expect(zonedTimeOfDayToUtc("06:30", "UTC", summer)).toBe("06:30");
  });

  it("round-trips through the zone", () => {
    for (const time of ["00:00", "06:15", "13:37", "23:45"]) {
      const zoned = utcTimeOfDayToZoned(time, "Europe/Zurich", summer);
      expect(zonedTimeOfDayToUtc(zoned, "Europe/Zurich", summer)).toBe(time);
    }
  });

  it("wraps across midnight UTC for early zone wall times", () => {
    // 01:00 CEST is 23:00 UTC the previous day — the caller must detect the
    // wrapped (start >= stop) window and reject it.
    expect(zonedTimeOfDayToUtc("01:00", "Europe/Zurich", summer)).toBe("23:00");
  });

  it("handles zones east of UTC crossing the date line", () => {
    expect(utcTimeOfDayToZoned("20:00", "Pacific/Auckland", winter)).toBe("09:00");
    expect(zonedTimeOfDayToUtc("09:00", "Pacific/Auckland", winter)).toBe("20:00");
  });
});
