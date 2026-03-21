import { SensorData, Webcam } from "@/data/types";

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

type FetchJsonOptions = RequestInit & {
  throwOnHttpError?: boolean;
};

export const createFallbackWebcam = (): Webcam => ({
  id: "",
  name: "Loading...",
  title: "Loading...",
  location: "",
  country: "",
  countryEmoji: "",
  coordinates: { lat: 0, lng: 0, altitude: 0 },
  currentImage: null,
  isOnline: undefined,
  lastUpdate: null,
  nextUpdate: null,
});

export const createFallbackStationScheduleConfig = (): StationScheduleConfig => ({
  cameraStartTime: "06:00",
  cameraStopTime: "20:00",
  useSunriseSunset: false,
  captureInterval: "30",
});

export const selectActiveWebcam = (webcams: Webcam[], activeWebcamId: string) =>
  webcams.find((webcam) => webcam.id === activeWebcamId) ?? webcams[0] ?? createFallbackWebcam();

export const isAbortError = (error: unknown): boolean =>
  error instanceof DOMException && error.name === "AbortError";

const stripTrailingSlash = (value: string): string => value.replace(/\/+$/, "");

export const resolveApiMediaUrl = (url: string | null | undefined, apiBaseUrl: string): string | null => {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  if (!url.startsWith("/")) return url;

  const normalizedBase = stripTrailingSlash(apiBaseUrl);
  if (!normalizedBase) return url;
  return `${normalizedBase}${url}`;
};

export const parseStationSummaryResponse = (item: StationSummaryResponse): Webcam => ({
  ...item,
});

export const parseStationDetailResponse = (item: StationDetailResponse, apiBaseUrl: string): Webcam => ({
  ...item,
  currentImage: resolveApiMediaUrl(item.currentImage, apiBaseUrl),
  lastUpdate: item.lastUpdate ? new Date(item.lastUpdate) : null,
  nextUpdate: item.nextUpdate ? new Date(item.nextUpdate) : null,
});

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

export const parseSensorDataResponse = (row: SensorDataResponse): SensorData => ({
  ...row,
  timestamp: new Date(row.timestamp),
});

export const parseTimelineItemResponse = (item: TimelineItemResponse, apiBaseUrl: string): TimelineImage => ({
  ...item,
  url: resolveApiMediaUrl(item.url, apiBaseUrl) ?? item.url,
  timestamp: new Date(item.timestamp),
});

export const fetchJson = async <T,>(url: string, options: FetchJsonOptions = {}): Promise<T | null> => {
  const { throwOnHttpError = true, ...requestInit } = options;
  const response = await fetch(url, requestInit);

  if (!response.ok) {
    if (throwOnHttpError) {
      throw new Error(`Request failed: ${response.status}`);
    }

    return null;
  }

  return (await response.json()) as T;
};
