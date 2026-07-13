import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SensorData, Webcam } from "@/data/types";
import {
  createStation as createStationRequest,
  deleteStation as deleteStationRequest,
  rotateStationDeviceSecret as rotateStationDeviceSecretRequest,
  DESCRIPTION_MAX_LENGTH,
  FALLBACK_STATION_SCHEDULE_CONFIG,
  FALLBACK_WEBCAM,
  flattenSensorSeries,
  getStationConfig,
  getStationDetail,
  getStationImageCaptures,
  getStationReadingEnvelopes,
  getStationSensorReadings,
  listStations,
  parseStationResponse,
  parseTimelineItemResponse,
  resolveStationSelection,
  StationCreatePayload,
  StationConfigResponse,
  StationScheduleConfig,
  TimelineImage,
  UNAVAILABLE_WEBCAM,
  updateStationConfig,
} from "@/api/stations";
import { DEFAULT_HISTORY_HOURS, MAX_HISTORY_HOURS } from "@/lib/historyFilters";
import { LOADING_LABEL } from "@/lib/placeholders";
import { getStationIdFromLocation, pushStationUrl } from "@/lib/stationLinks";

export type StationDataState = {
  activeWebcam: Webcam;
  setActiveWebcam: (webcam: Webcam) => void;
  webcamList: Webcam[];
  historicalData: SensorData[];
  historicalDataError: boolean;
  /** Lookback window (hours from now) the sensor history is fetched for. */
  historyWindowHours: number;
  setHistoryWindowHours: (hours: number) => void;
  imageTimeline: TimelineImage[];
  refreshImageTimeline: () => Promise<void>;
  createStation: (payload: StationCreatePayload) => Promise<{ success: boolean; stationId?: string; error?: string }>;
  deleteStation: (stationId: string) => Promise<{ success: boolean; error?: string }>;
  rotateDeviceSecret: (stationId: string) => Promise<{ success: boolean; secret?: string; error?: string }>;
  /** True while the initially selected station is still resolving (station
   * list or first station-data fetch) — drives the hero skeletons. */
  isStationLoading: boolean;
  stationStartTime: string;
  stationStopTime: string;
  useSunriseSunset: boolean;
  captureInterval: string;
  saveStationSchedule: (schedule: StationScheduleConfig) => Promise<boolean>;
  description: string;
  descriptionDraft: string;
  setDraftDescription: (description: string) => void;
  saveDescription: () => Promise<boolean>;
  isDescriptionSaving: boolean;
  descriptionError: string | null;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
  stationConfigError: string | null;
  isPublic: boolean;
  setIsPublic: (isPublic: boolean) => Promise<boolean>;
  canEdit: boolean;
};

// Playback ticks twice a second while playing, so it lives in its own context
// slice: only components that read it (the hero image) re-render on a tick.
export type PlaybackState = {
  currentImageIndex: number;
  setCurrentImageIndex: (index: number) => void;
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
};

export type WebcamDataState = {
  station: StationDataState;
  playback: PlaybackState;
};

type StationData = {
  stationId: string; // which station this payload belongs to (keepPreviousData can lag the key)
  detail: Webcam | null;
  timeline: TimelineImage[];
};

type StationHistory = {
  history: SensorData[];
  historyFailed: boolean; // the history request errored (distinct from "no readings")
};

// Poll cadence for station data and the stations list. A monitoring dashboard
// is often left open in a tab; without polling it would show the same image and
// online states forever (refetchOnWindowFocus is disabled app-wide).
const STATION_REFETCH_INTERVAL_MS = 5 * 60 * 1000;

// Auth state is part of the keys because the responses differ per auth state
// (private stations appear, `canEdit` flips on the detail): logging in or out
// must refetch rather than serve the anonymous answer from cache.
const stationsKey = (isAuthenticated: boolean) => ["stations", isAuthenticated] as const;
const stationDataKey = (stationId: string, isAuthenticated: boolean) =>
  ["station-data", stationId, isAuthenticated] as const;
const stationConfigKey = (stationId: string) => ["station-config", stationId] as const;

const GENERIC_SAVE_ERROR = "Unable to save the selected station settings.";

export const useWebcamData = (
  apiBaseUrl: string,
  isAuthenticated: boolean,
  authReady: boolean,
): WebcamDataState => {
  const queryClient = useQueryClient();

  // The user's station selection (URL-driven). The exposed activeWebcam is this
  // enriched with the detail/config query results below.
  const [selectedWebcam, setSelectedWebcam] = useState<Webcam>(() => {
    const urlStationId = getStationIdFromLocation(window.location);
    return urlStationId ? { ...FALLBACK_WEBCAM, id: urlStationId } : FALLBACK_WEBCAM;
  });
  const activeStationId = selectedWebcam.id;

  const [currentImageIndex, setCurrentImageIndexState] = useState(0);
  const [isPlaying, setIsPlayingState] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState("");
  const [descriptionError, setDescriptionError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  // Which save is currently in flight, so the schedule/visibility spinner and
  // the description spinner stay independent.
  const [savingKind, setSavingKind] = useState<null | "config" | "description">(null);

  // ---- Stations list ---------------------------------------------------------
  const stationsQuery = useQuery({
    queryKey: stationsKey(isAuthenticated),
    queryFn: async ({ signal }) => {
      const response = await listStations(apiBaseUrl, signal);
      return response ? response.map((item) => parseStationResponse(item)) : [];
    },
    refetchInterval: STATION_REFETCH_INTERVAL_MS, // keep sidebar/map online states fresh
    refetchOnWindowFocus: true,
  });
  const webcamList = useMemo(() => stationsQuery.data ?? [], [stationsQuery.data]);

  // Reconcile the selection whenever the list (re)loads. An unresolvable URL
  // token becomes the not-found state instead of silently showing a different
  // station (resolveStationSelection).
  useEffect(() => {
    if (stationsQuery.isError) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: mark unavailable when the stations list fails to load
      setSelectedWebcam(UNAVAILABLE_WEBCAM);
      return;
    }
    const list = stationsQuery.data;
    if (!list) return;
    setSelectedWebcam((current) => resolveStationSelection(list, current, authReady));
  }, [stationsQuery.data, stationsQuery.isError, authReady]);

  // Follow browser back/forward: re-read the station token from the URL and
  // re-select. setActiveWebcam pushes history entries with raw pushState (the
  // app deliberately doesn't remount the page per station), so without this
  // listener the address bar would change while the page kept its station.
  useEffect(() => {
    const handlePopState = () => {
      const ref = getStationIdFromLocation(window.location) ?? "";
      setSelectedWebcam((current) => {
        if (current.id === ref || (ref !== "" && current.urlSlug === ref)) return current;
        const base = { ...FALLBACK_WEBCAM, id: ref };
        const list = stationsQuery.data;
        return list ? resolveStationSelection(list, base, authReady) : base;
      });
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [stationsQuery.data, authReady]);

  // ---- Per-station data (detail + history + timeline) ------------------------
  const stationDataQuery = useQuery<StationData>({
    queryKey: stationDataKey(activeStationId, isAuthenticated),
    enabled: Boolean(activeStationId),
    // Keep the previous station's data visible while the newly-selected station
    // loads, so the sections above the map (hero, Data charts) don't collapse and
    // re-expand. That layout shift is what makes selecting a station on the map
    // appear to jump the page to the charts.
    placeholderData: keepPreviousData,
    // Poll for new captures/readings (paused while the tab is hidden) and
    // refresh immediately when the tab regains focus.
    refetchInterval: STATION_REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
    queryFn: async ({ signal }) => {
      const [detailResponse, timelineResponse] = await Promise.all([
        getStationDetail(apiBaseUrl, activeStationId, signal),
        getStationImageCaptures(apiBaseUrl, activeStationId, 48, signal),
      ]);
      return {
        stationId: activeStationId,
        detail: detailResponse ? parseStationResponse(detailResponse, apiBaseUrl) : null,
        timeline: timelineResponse
          ? timelineResponse.map((item) => parseTimelineItemResponse(item, apiBaseUrl))
          : [],
      };
    },
  });

  // ---- Sensor history (separate query: its lookback window is user-driven) ----
  // The Data panel's date picker widens the window up to the backend's 7-day
  // cap; keying the query on the window refetches just the history, not the
  // detail/timeline.
  const [historyWindowHours, setHistoryWindowHoursState] = useState(DEFAULT_HISTORY_HOURS);
  const setHistoryWindowHours = useCallback((hours: number) => {
    setHistoryWindowHoursState(Math.min(MAX_HISTORY_HOURS, Math.max(1, Math.round(hours))));
  }, []);
  const historyQuery = useQuery<StationHistory>({
    queryKey: ["station-history", activeStationId, isAuthenticated, historyWindowHours] as const,
    enabled: Boolean(activeStationId),
    placeholderData: keepPreviousData,
    refetchInterval: STATION_REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
    queryFn: async ({ signal }) => {
      const [historyResponse, envelopesResponse] = await Promise.all([
        getStationSensorReadings(apiBaseUrl, activeStationId, historyWindowHours, signal),
        getStationReadingEnvelopes(apiBaseUrl, activeStationId, historyWindowHours, signal),
      ]);
      return {
        history: historyResponse ? flattenSensorSeries(historyResponse, envelopesResponse ?? []) : [],
        historyFailed: historyResponse === null,
      };
    },
  });

  const historicalData = useMemo(() => historyQuery.data?.history ?? [], [historyQuery.data]);
  const historicalDataError = historyQuery.data?.historyFailed ?? false;
  const imageTimeline = useMemo(() => stationDataQuery.data?.timeline ?? [], [stationDataQuery.data]);

  // Initial resolution only: the list fetch, or a station's very first data
  // fetch (later switches keep showing the previous data via keepPreviousData).
  const isStationLoading = stationsQuery.isLoading || stationDataQuery.isLoading;

  // Whether the signed-in user may edit the active station (owner or admin),
  // sourced from the station detail. Until the detail loads we assume no, so the
  // owner-only settings (and their owner-only config fetch) never appear for a
  // viewer who can't use them.
  const activeStationDetail = stationDataQuery.data?.detail;
  const canEdit = Boolean(
    activeStationDetail && activeStationDetail.id === activeStationId && activeStationDetail.canEdit
  );
  // Owner-only config only applies once we're logged in and viewing a station.
  const hasOwnedStationContext = isAuthenticated && Boolean(activeStationId);

  // ---- Station config (owner-only) -------------------------------------------
  const configQuery = useQuery({
    queryKey: stationConfigKey(activeStationId),
    enabled: hasOwnedStationContext && canEdit,
    queryFn: ({ signal }) => getStationConfig(apiBaseUrl, activeStationId, signal),
  });
  const stationConfig = configQuery.data ?? null;

  // ---- Derived display station ----------------------------------------------
  const activeWebcam = useMemo<Webcam>(() => {
    let webcam = selectedWebcam;
    const detail = stationDataQuery.data?.detail;
    if (detail && detail.id === selectedWebcam.id) {
      webcam = { ...webcam, ...detail };
    }
    if (stationConfig) {
      webcam = { ...webcam, description: stationConfig.description, isPublic: stationConfig.isPublic };
    }
    return webcam;
  }, [selectedWebcam, stationDataQuery.data, stationConfig]);

  const schedule: StationScheduleConfig = stationConfig
    ? {
        stationStartTime: stationConfig.stationStartTime,
        stationStopTime: stationConfig.stationStopTime,
        useSunriseSunset: stationConfig.useSunriseSunset,
        captureInterval: String(stationConfig.captureIntervalMinutes),
      }
    : FALLBACK_STATION_SCHEDULE_CONFIG;
  const description = stationConfig?.description ?? selectedWebcam.description ?? "";
  const isPublic = stationConfig?.isPublic ?? selectedWebcam.isPublic ?? true;

  const isStationConfigLoading = hasOwnedStationContext && configQuery.isLoading;
  const configLoadFailed =
    hasOwnedStationContext &&
    (configQuery.isError || (configQuery.isSuccess && configQuery.data === null));
  const stationConfigError =
    saveError ?? (configLoadFailed ? "Unable to load the selected station settings." : null);

  // Seed the editable description draft once per station, when its config loads.
  const draftLoadedForRef = useRef<string | null>(null);
  useEffect(() => {
    if (!isAuthenticated || !activeStationId) {
      draftLoadedForRef.current = null;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: clear the description draft when leaving a station
      setDescriptionDraft("");
      setDescriptionError(null);
      return;
    }
    if (stationConfig && draftLoadedForRef.current !== activeStationId) {
      draftLoadedForRef.current = activeStationId;
      setDescriptionDraft(stationConfig.description ?? "");
      setDescriptionError(null);
    }
  }, [isAuthenticated, activeStationId, stationConfig]);

  // Reset transient errors and playback when the station changes.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: reset transient errors/playback when the station changes
    setSaveError(null);
    setCurrentImageIndexState(0);
    setIsPlayingState(false);
  }, [activeStationId]);

  // Image-timeline cursor: jump to the newest image when a station's timeline
  // first loads. On a refresh of the SAME station (poll or manual), follow the
  // newest only if the viewer was already there — otherwise keep the image they
  // scrubbed to, re-located by URL since the capped timeline drops its oldest
  // entries as new captures arrive.
  const seenTimelineRef = useRef<{ stationId: string; timeline: TimelineImage[] } | null>(null);
  useEffect(() => {
    const data = stationDataQuery.data;
    if (!data) return;
    const previous = seenTimelineRef.current;
    seenTimelineRef.current = { stationId: data.stationId, timeline: data.timeline };
    const latestIndex = Math.max(data.timeline.length - 1, 0);
    if (!previous || previous.stationId !== data.stationId) {
      setCurrentImageIndexState(latestIndex);
      setIsPlayingState(false);
      return;
    }
    setCurrentImageIndexState((currentIndex) => {
      if (currentIndex >= previous.timeline.length - 1) return latestIndex;
      const viewed = previous.timeline[currentIndex];
      if (!viewed) return latestIndex;
      const nextIndex = data.timeline.findIndex((image) => image.url === viewed.url);
      return nextIndex >= 0 ? nextIndex : Math.min(currentIndex, latestIndex);
    });
  }, [stationDataQuery.data]);

  // ---- Config mutation (optimistic, with rollback) ---------------------------
  const configMutation = useMutation({
    mutationFn: async (vars: { stationId: string; config: StationConfigResponse }) => {
      const response = await updateStationConfig(apiBaseUrl, vars.stationId, vars.config);
      if (!response) throw new Error("Station settings save failed.");
      return response;
    },
    onMutate: async ({ stationId, config }) => {
      await queryClient.cancelQueries({ queryKey: stationConfigKey(stationId) });
      const previousConfig = queryClient.getQueryData<StationConfigResponse | null>(
        stationConfigKey(stationId)
      );
      const previousStations = queryClient.getQueryData<Webcam[]>(stationsKey(isAuthenticated));
      queryClient.setQueryData(stationConfigKey(stationId), config);
      queryClient.setQueryData<Webcam[]>(stationsKey(isAuthenticated), (list) =>
        list?.map((webcam) =>
          webcam.id === stationId ? { ...webcam, isPublic: config.isPublic } : webcam
        )
      );
      return { previousConfig, previousStations, stationId };
    },
    onError: (_error, _vars, context) => {
      if (!context) return;
      queryClient.setQueryData(stationConfigKey(context.stationId), context.previousConfig);
      queryClient.setQueryData(stationsKey(isAuthenticated), context.previousStations);
    },
    onSuccess: (response, { stationId }) => {
      queryClient.setQueryData(stationConfigKey(stationId), response);
    },
  });
  const isStationConfigSaving = savingKind === "config";
  const isDescriptionSaving = savingKind === "description";

  const saveConfig = useCallback(
    async (nextConfig: StationConfigResponse, kind: "config" | "description"): Promise<boolean> => {
      if (!activeStationId || !isAuthenticated || !stationConfig) return false;
      setSavingKind(kind);
      setSaveError(null);
      try {
        await configMutation.mutateAsync({ stationId: activeStationId, config: nextConfig });
        return true;
      } catch {
        return false;
      } finally {
        setSavingKind((current) => (current === kind ? null : current));
      }
    },
    [activeStationId, configMutation, isAuthenticated, stationConfig]
  );

  const saveStationSchedule = useCallback(
    async (nextSchedule: StationScheduleConfig) => {
      if (!stationConfig) return false;
      const nextConfig: StationConfigResponse = {
        ...stationConfig,
        stationStartTime: nextSchedule.stationStartTime,
        stationStopTime: nextSchedule.stationStopTime,
        useSunriseSunset: nextSchedule.useSunriseSunset,
        captureIntervalMinutes: Number(nextSchedule.captureInterval),
      };
      const ok = await saveConfig(nextConfig, "config");
      if (!ok) setSaveError(GENERIC_SAVE_ERROR);
      return ok;
    },
    [saveConfig, stationConfig]
  );

  const saveDescription = useCallback(async () => {
    if (!stationConfig || !activeStationId || !isAuthenticated) return false;
    if (descriptionDraft.length > DESCRIPTION_MAX_LENGTH) {
      setDescriptionError(`Description must be ${DESCRIPTION_MAX_LENGTH} characters or fewer.`);
      return false;
    }
    const nextDescription = descriptionDraft.slice(0, DESCRIPTION_MAX_LENGTH);
    setDescriptionError(null);
    const ok = await saveConfig({ ...stationConfig, description: nextDescription }, "description");
    setDescriptionDraft(nextDescription);
    if (!ok) setDescriptionError("Unable to save the station description.");
    return ok;
  }, [activeStationId, descriptionDraft, isAuthenticated, saveConfig, stationConfig]);

  const setIsPublic = useCallback(
    async (nextIsPublic: boolean) => {
      if (!stationConfig || stationConfig.isPublic === nextIsPublic) return false;
      const ok = await saveConfig({ ...stationConfig, isPublic: nextIsPublic }, "config");
      if (!ok) setSaveError("Unable to update station visibility.");
      return ok;
    },
    [saveConfig, stationConfig]
  );

  // ---- Document title --------------------------------------------------------
  useEffect(() => {
    // Don't stamp the placeholder into the tab title / og:title while loading.
    if (activeWebcam.name === LOADING_LABEL) return;
    const title = `${activeWebcam.name} | Eagleshot`;
    document.title = title;
    document.querySelector('meta[property="og:title"]')?.setAttribute("content", title);
    document.querySelector('meta[name="twitter:site"]')?.setAttribute("content", title);
  }, [activeWebcam.name]);

  // ---- Image playback --------------------------------------------------------
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentImageIndexState((currentValue) => {
        if (currentValue >= imageTimeline.length - 1) {
          setIsPlayingState(false);
          return currentValue;
        }
        return currentValue + 1;
      });
    }, 500);
    return () => clearInterval(interval);
  }, [imageTimeline.length, isPlaying]);

  // ---- Imperative actions ----------------------------------------------------
  const setActiveWebcam = useCallback((webcam: Webcam) => {
    // Browser URL uses the pretty, editable slug; data calls use webcam.id.
    pushStationUrl(webcam.urlSlug || webcam.id);
    setSelectedWebcam(webcam);
  }, []);
  const setCurrentImageIndex = useCallback((index: number) => setCurrentImageIndexState(index), []);
  const setIsPlaying = useCallback((playing: boolean) => setIsPlayingState(playing), []);
  const setDraftDescription = useCallback((value: string) => {
    setDescriptionDraft(value.slice(0, DESCRIPTION_MAX_LENGTH));
    setDescriptionError(null);
  }, []);

  const refreshImageTimeline = useCallback(async () => {
    await stationDataQuery.refetch();
  }, [stationDataQuery]);

  const createStation = useCallback(
    async (payload: StationCreatePayload) => {
      if (!isAuthenticated) {
        return { success: false, error: "Sign in before creating a station." };
      }
      const result = await createStationRequest(apiBaseUrl, payload);
      if (!result.success || !result.station) {
        return { success: false, error: result.error ?? "Unable to create station." };
      }
      const parsedStation = parseStationResponse(result.station, apiBaseUrl);
      queryClient.setQueryData<Webcam[]>(stationsKey(isAuthenticated), (list) => {
        const existing = list ?? [];
        return existing.some((webcam) => webcam.id === parsedStation.id)
          ? existing.map((webcam) => (webcam.id === parsedStation.id ? parsedStation : webcam))
          : [...existing, parsedStation];
      });
      pushStationUrl(parsedStation.urlSlug || parsedStation.id);
      setSelectedWebcam(parsedStation);
      return { success: true, stationId: parsedStation.id };
    },
    [apiBaseUrl, isAuthenticated, queryClient]
  );

  const rotateDeviceSecret = useCallback(
    (stationId: string) => rotateStationDeviceSecretRequest(apiBaseUrl, stationId),
    [apiBaseUrl]
  );

  const deleteStation = useCallback(
    async (stationId: string) => {
      if (!isAuthenticated) {
        return { success: false, error: "Sign in before deleting a station." };
      }
      const result = await deleteStationRequest(apiBaseUrl, stationId);
      if (!result.success) return result;
      // Drop the dead station's cached data (both auth variants of the key)
      // and prune it from the list, then move the selection to what's left.
      queryClient.removeQueries({ queryKey: ["station-data", stationId] });
      queryClient.removeQueries({ queryKey: stationConfigKey(stationId) });
      let nextSelection: Webcam | undefined;
      queryClient.setQueryData<Webcam[]>(stationsKey(isAuthenticated), (list) => {
        const remaining = (list ?? []).filter((webcam) => webcam.id !== stationId);
        nextSelection = remaining[0];
        return remaining;
      });
      if (nextSelection) {
        pushStationUrl(nextSelection.urlSlug || nextSelection.id);
        setSelectedWebcam(nextSelection);
      } else {
        window.history.pushState(null, "", "/");
        setSelectedWebcam(UNAVAILABLE_WEBCAM);
      }
      return { success: true };
    },
    [apiBaseUrl, isAuthenticated, queryClient]
  );

  const station = useMemo<StationDataState>(
    () => ({
      activeWebcam,
      setActiveWebcam,
      webcamList,
      historicalData,
      historicalDataError,
      historyWindowHours,
      setHistoryWindowHours,
      imageTimeline,
      isStationLoading,
      refreshImageTimeline,
      createStation,
      deleteStation,
      rotateDeviceSecret,
      stationStartTime: schedule.stationStartTime,
      stationStopTime: schedule.stationStopTime,
      useSunriseSunset: schedule.useSunriseSunset,
      captureInterval: schedule.captureInterval,
      saveStationSchedule,
      description,
      descriptionDraft,
      setDraftDescription,
      saveDescription,
      isDescriptionSaving,
      descriptionError,
      isStationConfigLoading,
      isStationConfigSaving,
      stationConfigError,
      isPublic,
      setIsPublic,
      canEdit,
    }),
    [
      activeWebcam,
      canEdit,
      createStation,
      deleteStation,
      description,
      descriptionDraft,
      descriptionError,
      historicalData,
      historicalDataError,
      historyWindowHours,
      imageTimeline,
      isDescriptionSaving,
      isStationLoading,
      isPublic,
      isStationConfigLoading,
      isStationConfigSaving,
      refreshImageTimeline,
      rotateDeviceSecret,
      saveDescription,
      saveStationSchedule,
      schedule.captureInterval,
      schedule.stationStartTime,
      schedule.stationStopTime,
      schedule.useSunriseSunset,
      setActiveWebcam,
      setDraftDescription,
      setHistoryWindowHours,
      setIsPublic,
      stationConfigError,
      webcamList,
    ]
  );

  const playback = useMemo<PlaybackState>(
    () => ({
      currentImageIndex,
      setCurrentImageIndex,
      isPlaying,
      setIsPlaying,
    }),
    [currentImageIndex, isPlaying, setCurrentImageIndex, setIsPlaying]
  );

  return useMemo(() => ({ station, playback }), [station, playback]);
};
