import { describe, expect, it } from "vitest";

import { getCountryOptions, getFlagEmojiFromCountryName } from "@/lib/location";

describe("getCountryOptions", () => {
  it("returns a populated, sorted country list (regression: it was silently empty)", () => {
    const options = getCountryOptions();

    expect(options.length).toBeGreaterThan(150);
    const names = options.map((option) => option.name);
    expect([...names].sort((a, b) => a.localeCompare(b))).toEqual(names);

    const switzerland = options.find((option) => option.code === "CH");
    expect(switzerland?.name).toBe("Switzerland");
    expect(switzerland?.flag).toBe("\u{1F1E8}\u{1F1ED}");
  });

  it("every dropdown name resolves back to its flag", () => {
    for (const option of getCountryOptions()) {
      expect(getFlagEmojiFromCountryName(option.name), option.name).toBe(option.flag);
    }
  });
});
