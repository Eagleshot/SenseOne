import { SensorData, Webcam } from "@/data/types";
import { apiBaseUrl, extractErrorDetail, fetchJson } from "@/lib/apiClient";
import { LOADING_LABEL, UNAVAILABLE_LABEL } from "@/lib/placeholders";

export type WebcamCoordinatesResponse = {
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
  isPublic?: boolean;
};

export type StationDetailResponse = StationSummaryResponse & {
  description?: string;
  country?: string;
  countryEmoji?: string;
  battery?: number | null;
  currentImage?: string | null;
  isOnline?: boolean;
  lastUpdate?: string | null;
  nextUpdate?: string | null;
  firmwareVersion?: string | null;
  wakeReason?: string | null;
};

export type StationConfigResponse = {
  stationStartTime: string;
  stationStopTime: string;
  useSunriseSunset: boolean;
  captureIntervalMinutes: number;
  title: string;
  description: string;
  lat: number;
  lon: number;
  alt: number;
  location: string;
  country: string;
  countryEmoji: string;
  isPublic: boolean;
  lastOnline?: string | null;
  nextOnline?: string | null;
};

export type StationCreatePayload = {
  title: string;
  location: string;
  country: string;
  countryEmoji: string;
  lat: number;
  lon: number;
  alt: number;
  isPublic: boolean;
};

export type StationCreateResult = {
  success: boolean;
  station?: StationDetailResponse;
  error?: string;
};

export type StationScheduleConfig = {
  stationStartTime: string;
  stationStopTime: string;
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
  stationStartTime: "06:00",
  stationStopTime: "20:00",
  useSunriseSunset: false,
  captureInterval: "30",
};

export const selectActiveWebcam = (webcams: Webcam[], activeWebcamId: string) =>
  webcams.find((webcam) => webcam.id === activeWebcamId) ?? webcams[0] ?? FALLBACK_WEBCAM;

export const resolveApiMediaUrl = (url: string | null | undefined, baseUrl: string): string | null => {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  if (!url.startsWith("/")) return url;

  const normalizedBase = baseUrl.replace(/\/+$/, "");
  if (!normalizedBase) return url;
  return `${normalizedBase}${url}`;
};

// Python-generated mock data includes microsecond precision, which some browsers
// parse inconsistently. Trim to milliseconds before constructing Date objects.
export const parseApiTimestamp = (value: string): Date =>
  new Date(value.replace(/(\.\d{3})\d+(?=(?:Z|[+-]\d{2}:\d{2})$)/, "$1"));

export const parseStationResponse = (
  item: StationDetailResponse | StationSummaryResponse,
  baseUrl?: string
): Webcam => {
  const baseItem = item as StationDetailResponse;
  return {
    ...item,
    isPublic: item.isPublic ?? true,
    currentImage: baseUrl ? resolveApiMediaUrl(baseItem.currentImage, baseUrl) : (baseItem.currentImage ?? null),
    lastUpdate: baseItem.lastUpdate ? parseApiTimestamp(baseItem.lastUpdate) : null,
    nextUpdate: baseItem.nextUpdate ? parseApiTimestamp(baseItem.nextUpdate) : null,
  };
};

export const parseTimestampResponse = <
  T extends { timestamp: string },
  U extends Omit<T, "timestamp"> & { timestamp: Date },
>(
  item: T
): U => ({
  ...item,
  timestamp: parseApiTimestamp(item.timestamp),
} as unknown as U);

export const parseTimelineItemResponse = (item: TimelineItemResponse, baseUrl: string): TimelineImage => ({
  ...item,
  url: resolveApiMediaUrl(item.url, baseUrl) ?? item.url,
  timestamp: parseApiTimestamp(item.timestamp),
});

export const stationPath = (stationId: string, suffix = "", baseUrl = apiBaseUrl): string =>
  `${baseUrl}/stations/${encodeURIComponent(stationId)}${suffix}`;

export const listStations = (baseUrl: string, signal?: AbortSignal) =>
  fetchJson<StationSummaryResponse[]>(`${baseUrl}/stations`, {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

export const createStation = async (
  baseUrl: string,
  payload: StationCreatePayload
): Promise<StationCreateResult> => {
  try {
    const response = await fetch(`${baseUrl}/stations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const fallback =
        response.status === 401
          ? "Sign in again before creating a station."
          : "Unable to create station.";
      let message = fallback;

      try {
        const body = await response.json();
        message = extractErrorDetail(body, fallback);
      } catch {
        // Keep fallback when the response body is empty or invalid JSON.
      }

      return { success: false, error: message };
    }

    const station = (await response.json()) as StationDetailResponse;
    return { success: true, station };
  } catch {
    return { success: false, error: "Unable to reach station service." };
  }
};

export type DeviceSecretResult = {
  success: boolean;
  secret?: string;
  error?: string;
};

export const rotateStationDeviceSecret = async (
  baseUrl: string,
  stationId: string
): Promise<DeviceSecretResult> => {
  try {
    const response = await fetch(`${baseUrl}/stations/${encodeURIComponent(stationId)}/rotate-device-secret`, {
      method: "POST",
      credentials: "include",
    });

    if (!response.ok) {
      const fallback =
        response.status === 401
          ? "Sign in again to provision a device secret."
          : "Unable to provision a device secret.";
      let message = fallback;
      try {
        message = extractErrorDetail(await response.json(), fallback);
      } catch {
        // Keep fallback when the response body is empty or invalid JSON.
      }
      return { success: false, error: message };
    }

    const body = (await response.json()) as { deviceHmacSecret?: string };
    if (!body.deviceHmacSecret) {
      return { success: false, error: "Device secret missing from response." };
    }
    return { success: true, secret: body.deviceHmacSecret };
  } catch {
    return { success: false, error: "Unable to reach station service." };
  }
};

export const getStationConfig = (baseUrl: string, stationId: string, signal?: AbortSignal) =>
  fetchJson<StationConfigResponse>(stationPath(stationId, "/config", baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

export const updateStationConfig = (baseUrl: string, stationId: string, config: StationConfigResponse) =>
  fetchJson<StationConfigResponse>(stationPath(stationId, "/config", baseUrl), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
    credentials: "include",
    throwOnHttpError: false,
  });

export const getStationDetail = (baseUrl: string, stationId: string, signal?: AbortSignal) =>
  fetchJson<StationDetailResponse>(stationPath(stationId, "", baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

export const getStationSensorReadings = (baseUrl: string, stationId: string, hours: number, signal?: AbortSignal) =>
  fetchJson<SensorDataResponse[]>(stationPath(stationId, `/sensor-readings?hours=${hours}`, baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

export const getStationImageCaptures = (baseUrl: string, stationId: string, count: number, signal?: AbortSignal) =>
  fetchJson<TimelineItemResponse[]>(stationPath(stationId, `/image-captures?count=${count}`, baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

