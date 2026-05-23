import { describe, expect, it } from "vitest";

import {
  CAPTURE_INTERVAL_OPTIONS,
  CUSTOM_CAPTURE_INTERVAL_VALUE,
  getCaptureIntervalSelection,
  getCustomCaptureIntervalInput,
  isPresetCaptureInterval,
  normalizeCaptureInterval,
  validateCaptureInterval,
} from "@/lib/captureInterval";

describe("captureInterval", () => {
  it("identifies preset interval values", () => {
    expect(isPresetCaptureInterval(CAPTURE_INTERVAL_OPTIONS[0].value)).toBe(true);
    expect(isPresetCaptureInterval("17")).toBe(false);
  });

  it("returns the correct selection value for preset and custom intervals", () => {
    expect(getCaptureIntervalSelection("30")).toBe("30");
    expect(getCaptureIntervalSelection("17")).toBe(CUSTOM_CAPTURE_INTERVAL_VALUE);
  });

  it("keeps custom values in the custom input", () => {
    expect(getCustomCaptureIntervalInput("30")).toBe("");
    expect(getCustomCaptureIntervalInput("17")).toBe("17");
  });

  it("validates blank and out-of-range intervals", () => {
    expect(validateCaptureInterval("")).toBe("Enter a custom interval in minutes.");
    expect(validateCaptureInterval("0")).toContain("between 1 and 1440");
    expect(validateCaptureInterval("1.5")).toContain("between 1 and 1440");
  });

  it("normalizes valid custom intervals", () => {
    expect(validateCaptureInterval("120")).toBeNull();
    expect(normalizeCaptureInterval("120")).toBe("120");
    expect(normalizeCaptureInterval(" 45 ")).toBe("45");
  });
});

