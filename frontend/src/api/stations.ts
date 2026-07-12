import { SensorData, Webcam } from "@/data/types";
import { apiBaseUrl, fetchJson, postJson } from "@/lib/apiClient";
import { LOADING_LABEL, NOT_FOUND_LABEL, UNAVAILABLE_LABEL } from "@/lib/placeholders";

export type WebcamCoordinatesResponse = {
  lat: number;
  lng: number;
  altitude: number;
};

export type StationSummaryResponse = {
  id: string;
  urlSlug?: string;
  name: string;
  location: string;
  country?: string;
  countryEmoji?: string;
  coordinates: WebcamCoordinatesResponse;
  isPublic?: boolean;
  canEdit?: boolean;
};

export type StationDetailResponse = StationSummaryResponse & {
  description?: string;
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

// The sensor-history endpoint returns one point series per (metric, channel).
export type SensorSeriesPointResponse = {
  timestamp: string;
  value: number;
};

export type SensorSeriesResponse = {
  metric: string;
  channel: string;
  unit: string | null;
  points: SensorSeriesPointResponse[];
};

// One entry per device check-in: the reading-envelope fields the metric series
// omit, so check-ins that reported no metrics still surface.
export type SensorReadingEnvelopeResponse = {
  timestamp: string;
  nextStart: string | null;
  firmwareVersion: string | null;
  wakeReason: string | null;
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

// Shown when the URL names a station the caller can't see (nonexistent or
// private to someone else). The page renders this instead of silently showing
// a different station than the address bar claims.
export const NOT_FOUND_WEBCAM: Webcam = {
  ...FALLBACK_WEBCAM,
  name: NOT_FOUND_LABEL,
  description: "This station does not exist or is private. Sign in if it is yours.",
};

export const FALLBACK_STATION_SCHEDULE_CONFIG: StationScheduleConfig = {
  stationStartTime: "06:00",
  stationStopTime: "20:00",
  useSunriseSunset: false,
  captureInterval: "30",
};

/**
 * Resolve which station the current selection refers to once the list is known.
 * `current.id` holds the URL token (stable id or editable url_slug) until it
 * resolves. A token that matches nothing becomes the not-found sentinel —
 * keeping the token so the same URL can resolve after sign-in — rather than
 * silently showing a different station than the address bar claims. While auth
 * is still settling (`authReady` false) the selection is left alone, since the
 * list refetches per auth state and a private station may yet appear.
 */
export const resolveStationSelection = (list: Webcam[], current: Webcam, authReady: boolean): Webcam => {
  if (list.length === 0) return { ...UNAVAILABLE_WEBCAM, id: current.id };
  const ref = current.id;
  if (!ref) return list[0];
  const matched = list.find((webcam) => webcam.id === ref || webcam.urlSlug === ref);
  if (matched) return matched;
  return authReady ? { ...NOT_FOUND_WEBCAM, id: ref } : current;
};

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
  const result = await postJson<StationDetailResponse>(`${baseUrl}/stations`, {
    body: payload,
    errorFallback: (status) =>
      status === 401 ? "Sign in again before creating a station." : "Unable to create station.",
    networkError: "Unable to reach station service.",
  });
  return result.ok
    ? { success: true, station: result.data }
    : { success: false, error: result.error };
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
  const result = await postJson<{ deviceHmacSecret?: string }>(
    `${baseUrl}/stations/${encodeURIComponent(stationId)}/rotate-device-secret`,
    {
      errorFallback: (status) =>
        status === 401 ? "Sign in again to provision a device secret." : "Unable to provision a device secret.",
      networkError: "Unable to reach station service.",
    },
  );
  if (!result.ok) return { success: false, error: result.error };
  if (!result.data.deviceHmacSecret) {
    return { success: false, error: "Device secret missing from response." };
  }
  return { success: true, secret: result.data.deviceHmacSecret };
};

export type StationDeleteResult = { success: boolean; error?: string };

/** Permanently delete a station (owner/admin only). The backend removes the
 * row, its history, and the stored image files; returns 204 on success. */
export const deleteStation = async (baseUrl: string, stationId: string): Promise<StationDeleteResult> => {
  const result = await postJson<void>(stationPath(stationId, "", baseUrl), {
    method: "DELETE",
    errorFallback: (status) =>
      status === 401
        ? "Sign in again to delete this station."
        : status === 403
          ? "Only the station owner can delete it."
          : "Unable to delete the station.",
    networkError: "Unable to reach station service.",
  });
  return result.ok ? { success: true } : { success: false, error: result.error };
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

// The primary sensor channel; only this channel is folded into the flat chart
// rows for now. Multi-channel display is a follow-up.
export const DEFAULT_SENSOR_CHANNEL = "default";

export const getStationSensorReadings = (baseUrl: string, stationId: string, hours: number, signal?: AbortSignal) =>
  fetchJson<SensorSeriesResponse[]>(stationPath(stationId, `/data?hours=${hours}`, baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

export const getStationReadingEnvelopes = (baseUrl: string, stationId: string, hours: number, signal?: AbortSignal) =>
  fetchJson<SensorReadingEnvelopeResponse[]>(stationPath(stationId, `/readings?hours=${hours}`, baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

// Pivot the per-(metric, channel) series into the flat, timestamp-keyed rows the
// charts/tables consume. Only the default channel is folded in; each row gathers
// every metric reported at that timestamp. Rows are ordered oldest-to-newest.
export const flattenSensorSeries = (
  series: SensorSeriesResponse[],
  envelopes: SensorReadingEnvelopeResponse[] = [],
): SensorData[] => {
  const rowsByTimestamp = new Map<string, SensorData>();
  const rowFor = (timestamp: string): SensorData => {
    let row = rowsByTimestamp.get(timestamp);
    if (!row) {
      row = { timestamp: parseApiTimestamp(timestamp) };
      rowsByTimestamp.set(timestamp, row);
    }
    return row;
  };

  for (const stream of series) {
    if (stream.channel !== DEFAULT_SENSOR_CHANNEL) continue;
    for (const point of stream.points) {
      rowFor(point.timestamp)[stream.metric] = point.value;
    }
  }
  // Merge per-reading envelopes by timestamp (== the observations' recorded_at):
  // a check-in with no metrics still gets a row, and every row carries its
  // next-start time plus the device labels.
  for (const envelope of envelopes) {
    const row = rowFor(envelope.timestamp);
    row.nextStart = envelope.nextStart ? parseApiTimestamp(envelope.nextStart) : null;
    if (envelope.wakeReason) row.wakeReason = envelope.wakeReason;
    if (envelope.firmwareVersion) row.firmwareVersion = envelope.firmwareVersion;
  }
  return Array.from(rowsByTimestamp.values()).sort(
    (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
  );
};

export const getStationImageCaptures = (baseUrl: string, stationId: string, count: number, signal?: AbortSignal) =>
  fetchJson<TimelineItemResponse[]>(stationPath(stationId, `/image-captures?count=${count}`, baseUrl), {
    credentials: "include",
    signal,
    throwOnHttpError: false,
  });

