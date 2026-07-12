import { TimezoneOption } from "./types";

// Curated fallback for engines without Intl.supportedValuesOf.
const FALLBACK_TIMEZONES: TimezoneOption[] = [
  { value: "UTC", label: "UTC" },
  { value: "Europe/Zurich", label: "Europe/Zurich" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Europe/Paris", label: "Europe/Paris" },
  { value: "America/New_York", label: "America/New York" },
  { value: "America/Los_Angeles", label: "America/Los Angeles" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
];

// The full IANA timezone list from the runtime (~400 zones, already sorted),
// so any browser timezone is selectable; the picker provides search.
const buildTimezoneOptions = (): TimezoneOption[] => {
  try {
    if (typeof Intl !== "undefined" && typeof Intl.supportedValuesOf === "function") {
      const zones = Intl.supportedValuesOf("timeZone");
      const options = zones.map((value) => ({ value, label: value.replace(/_/g, " ") }));
      if (!zones.includes("UTC")) options.unshift({ value: "UTC", label: "UTC" });
      return options;
    }
  } catch {
    // Fall through to the curated list.
  }
  return FALLBACK_TIMEZONES;
};

export const TIMEZONES: TimezoneOption[] = buildTimezoneOptions();
