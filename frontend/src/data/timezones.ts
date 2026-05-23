import { TimezoneOption } from "./types";

export const TIMEZONES: TimezoneOption[] = [
  { value: "UTC", label: "UTC" },
  { value: "Europe/Zurich", label: "Zurich (CET/CEST)" },
  { value: "Europe/London", label: "London (GMT/BST)" },
  { value: "Europe/Paris", label: "Paris (CET/CEST)" },
  { value: "America/New_York", label: "New York (EST/EDT)" },
  { value: "America/Los_Angeles", label: "Los Angeles (PST/PDT)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
];
