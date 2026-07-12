import { describe, expect, it } from "vitest";

import { TIMEZONES } from "@/data/timezones";

describe("TIMEZONES", () => {
  it("offers the full IANA list, not a hand-picked handful", () => {
    expect(TIMEZONES.length).toBeGreaterThan(100);
  });

  it("includes UTC and common zones with readable labels", () => {
    const values = TIMEZONES.map((tz) => tz.value);
    expect(values).toContain("UTC");
    expect(values).toContain("Europe/Zurich");
    expect(values).toContain("Asia/Bangkok"); // seed stations live here

    const newYork = TIMEZONES.find((tz) => tz.value === "America/New_York");
    expect(newYork?.label).toBe("America/New York"); // underscores prettified
  });
});
