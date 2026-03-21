export const CUSTOM_CAPTURE_INTERVAL_VALUE = "custom";

export const CAPTURE_INTERVAL_OPTIONS = [
  { value: "5", label: "5 min" },
  { value: "10", label: "10 min" },
  { value: "15", label: "15 min" },
  { value: "30", label: "30 min" },
  { value: "60", label: "60 min" },
] as const;

const PRESET_CAPTURE_INTERVAL_VALUES = new Set(CAPTURE_INTERVAL_OPTIONS.map((option) => option.value));
const MIN_CAPTURE_INTERVAL_MINUTES = 1;
const MAX_CAPTURE_INTERVAL_MINUTES = 1440;

export const isPresetCaptureInterval = (value: string) => PRESET_CAPTURE_INTERVAL_VALUES.has(value);

export const getCaptureIntervalSelection = (value: string) =>
  isPresetCaptureInterval(value) ? value : CUSTOM_CAPTURE_INTERVAL_VALUE;

export const getCustomCaptureIntervalInput = (value: string) => (isPresetCaptureInterval(value) ? "" : value);

export const validateCaptureInterval = (value: string) => {
  if (!value.trim()) {
    return "Enter a custom interval in minutes.";
  }

  const numericValue = Number(value);
  if (
    !Number.isInteger(numericValue) ||
    numericValue < MIN_CAPTURE_INTERVAL_MINUTES ||
    numericValue > MAX_CAPTURE_INTERVAL_MINUTES
  ) {
    return `Interval must be an integer between ${MIN_CAPTURE_INTERVAL_MINUTES} and ${MAX_CAPTURE_INTERVAL_MINUTES} minutes.`;
  }

  return null;
};

export const normalizeCaptureInterval = (value: string) => {
  const error = validateCaptureInterval(value);
  return error ? null : String(Number(value));
};
