import { SensorData, Webcam } from "@/data/types";
import { fetchJson, isAbortError } from "@/lib/apiClient";
import { LOADING_LABEL, UNAVAILABLE_LABEL } from "@/lib/placeholders";

export { fetchJson, isAbortError };

type WebcamCoordinatesResponse = {
  lat: number;
  lng: number;
  altitude: number;
};

export type StationSummaryResponse = {
  id: string;
  name: string;
  location: string;
  country?: string;
  countryEmoji?: string;
  battery?: number | null;
  coordinates: WebcamCoordinatesResponse;
};

export type StationDetailResponse = StationSummaryResponse & {
  description?: string;
  country?: string;
  countryEmoji?: string;
  currentImage?: string | null;
  isOnline?: boolean;
  lastUpdate?: string | null;
  nextUpdate?: string | null;
};

export type StationConfigResponse = {
  camera_start_time: string;
  camera_stop_time: string;
  use_sunrise_sunset: boolean;
  capture_interval_minutes: number;
  title: string;
  description: string;
  lat: number;
  lon: number;
  alt: number;
  location: string;
  country: string;
  country_emoji: string;
  is_online?: boolean | null;
  last_online?: string | null;
  next_online?: string | null;
};

export type StationScheduleConfig = {
  cameraStartTime: string;
  cameraStopTime: string;
  useSunriseSunset: boolean;
  captureInterval: string;
};

export type SensorDataResponse = Omit<SensorData, "timestamp"> & {
  timestamp: string;
};

export type TimelineItemResponse = {
  timestamp: string;
  url: string;
};

export type LoginResponse = {
  expires_in: number;
  username: string;
};

export type MeResponse = {
  username: string;
};

export type TimelineImage = {
  timestamp: Date;
  url: string;
};

export const DESCRIPTION_MAX_LENGTH = 500;

export const FALLBACK_WEBCAM: Webcam = {
  id: "",
  name: LOADING_LABEL,
  location: "",
  country: "",
  countryEmoji: "",
  coordinates: { lat: 0, lng: 0, altitude: 0 },
  currentImage: null,
  isOnline: undefined,
  lastUpdate: null,
  nextUpdate: null,
};

export const UNAVAILABLE_WEBCAM: Webcam = {
  ...FALLBACK_WEBCAM,
  name: UNAVAILABLE_LABEL,
};

export const FALLBACK_STATION_SCHEDULE_CONFIG: StationScheduleConfig = {
  cameraStartTime: "06:00",
  cameraStopTime: "20:00",
  useSunriseSunset: false,
  captureInterval: "30",
};

export const selectActiveWebcam = (webcams: Webcam[], activeWebcamId: string) =>
  webcams.find((webcam) => webcam.id === activeWebcamId) ?? webcams[0] ?? FALLBACK_WEBCAM;

export const resolveApiMediaUrl = (url: string | null | undefined, apiBaseUrl: string): string | null => {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  if (!url.startsWith("/")) return url;

  const normalizedBase = apiBaseUrl.replace(/\/+$/, "");
  if (!normalizedBase) return url;
  return `${normalizedBase}${url}`;
};

// Python-generated mock data includes microsecond precision, which some browsers
// parse inconsistently. Trim to milliseconds before constructing Date objects.
export const parseApiTimestamp = (value: string): Date =>
  new Date(value.replace(/(\.\d{3})\d+(?=(?:Z|[+-]\d{2}:\d{2})$)/, "$1"));

/** Transform station response (summary or detail) to Webcam. */
export const parseStationResponse = (item: StationDetailResponse | StationSummaryResponse, apiBaseUrl?: string): Webcam => {
  const baseItem = item as StationDetailResponse;
  return {
    ...item,
    currentImage: apiBaseUrl ? resolveApiMediaUrl(baseItem.currentImage, apiBaseUrl) : (baseItem.currentImage ?? null),
    lastUpdate: baseItem.lastUpdate ? parseApiTimestamp(baseItem.lastUpdate) : null,
    nextUpdate: baseItem.nextUpdate ? parseApiTimestamp(baseItem.nextUpdate) : null,
  };
};

export const parseStationConfigResponse = (item: StationConfigResponse): StationScheduleConfig => ({
  cameraStartTime: item.camera_start_time,
  cameraStopTime: item.camera_stop_time,
  useSunriseSunset: item.use_sunrise_sunset,
  captureInterval: String(item.capture_interval_minutes),
});

export const createStationConfigRequest = (
  currentConfig: StationConfigResponse,
  updates: Partial<StationConfigResponse>
): StationConfigResponse => ({
  ...currentConfig,
  ...updates,
});

export const createStationScheduleUpdate = (schedule: StationScheduleConfig): Partial<StationConfigResponse> => ({
  camera_start_time: schedule.cameraStartTime,
  camera_stop_time: schedule.cameraStopTime,
  use_sunrise_sunset: schedule.useSunriseSunset,
  capture_interval_minutes: Number(schedule.captureInterval),
});

/** Transform API response with ISO timestamp to domain object with Date. */
export const parseTimestampResponse = <T extends { timestamp: string }, U extends Omit<T, "timestamp"> & { timestamp: Date }>(
  item: T
): U => ({
  ...item,
  timestamp: parseApiTimestamp(item.timestamp),
} as U);

export const parseTimelineItemResponse = (item: TimelineItemResponse, apiBaseUrl: string): TimelineImage => ({
  ...item,
  url: resolveApiMediaUrl(item.url, apiBaseUrl) ?? item.url,
  timestamp: parseApiTimestamp(item.timestamp),
});
