import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { TIMEZONES } from "@/data/timezones";
import { SensorData, Webcam } from "@/data/types";
import {
  createStation as createStationRequest,
  rotateStationDeviceSecret as rotateStationDeviceSecretRequest,
  DESCRIPTION_MAX_LENGTH,
  FALLBACK_STATION_SCHEDULE_CONFIG,
  FALLBACK_WEBCAM,
  getStationConfig,
  getStationDetail,
  getStationImageCaptures,
  getStationSensorReadings,
  listStations,
  parseStationResponse,
  parseTimestampResponse,
  parseTimelineItemResponse,
  selectActiveWebcam,
  StationCreatePayload,
  StationConfigResponse,
  StationScheduleConfig,
  TimelineImage,
  UNAVAILABLE_WEBCAM,
  updateStationConfig,
} from "@/api/stations";
import { getStationIdFromLocation, pushStationUrl } from "@/lib/stationLinks";

export type WebcamDataState = {
  activeWebcam: Webcam;
  setActiveWebcam: (webcam: Webcam) => void;
  webcamList: Webcam[];
  historicalData: SensorData[];
  imageTimeline: TimelineImage[];
  currentImageIndex: number;
  setCurrentImageIndex: (index: number) => void;
  refreshImageTimeline: () => Promise<void>;
  createStation: (payload: StationCreatePayload) => Promise<{ success: boolean; stationId?: string; error?: string }>;
  rotateDeviceSecret: (stationId: string) => Promise<{ success: boolean; secret?: string; error?: string }>;
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  timezones: typeof TIMEZONES;
  stationStartTime: string;
  stationStopTime: string;
  useSunriseSunset: boolean;
  captureInterval: string;
  saveStationSchedule: (schedule: StationScheduleConfig) => Promise<void>;
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
  setIsPublic: (isPublic: boolean) => Promise<void>;
};

type StationData = {
  detail: Webcam | null;
  history: SensorData[];
  timeline: TimelineImage[];
};

const stationsKey = (isAuthenticated: boolean) => ["stations", isAuthenticated] as const;
const stationDataKey = (stationId: string) => ["station-data", stationId] as const;
const stationConfigKey = (stationId: string) => ["station-config", stationId] as const;

const GENERIC_SAVE_ERROR = "Unable to save the selected station settings.";

export const useWebcamData = (apiBaseUrl: string, isAuthenticated: boolean): WebcamDataState => {
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
  });
  const webcamList = useMemo(() => stationsQuery.data ?? [], [stationsQuery.data]);

  // Reconcile the selection whenever the list (re)loads.
  useEffect(() => {
    if (stationsQuery.isError) {
      setSelectedWebcam(UNAVAILABLE_WEBCAM);
      return;
    }
    const list = stationsQuery.data;
    if (!list) return;
    setSelectedWebcam((current) =>
      list.length > 0 ? selectActiveWebcam(list, current.id) : UNAVAILABLE_WEBCAM
    );
  }, [stationsQuery.data, stationsQuery.isError]);

  // ---- Per-station data (detail + history + timeline) ------------------------
  const stationDataQuery = useQuery<StationData>({
    queryKey: stationDataKey(activeStationId),
    enabled: Boolean(activeStationId),
    queryFn: async ({ signal }) => {
      const [detailResponse, historyResponse, timelineResponse] = await Promise.all([
        getStationDetail(apiBaseUrl, activeStationId, signal),
        getStationSensorReadings(apiBaseUrl, activeStationId, 24, signal),
        getStationImageCaptures(apiBaseUrl, activeStationId, 48, signal),
      ]);
      return {
        detail: detailResponse ? parseStationResponse(detailResponse, apiBaseUrl) : null,
        history: historyResponse ? historyResponse.map(parseTimestampResponse) : [],
        timeline: timelineResponse
          ? timelineResponse.map((item) => parseTimelineItemResponse(item, apiBaseUrl))
          : [],
      };
    },
  });

  const historicalData = useMemo(() => stationDataQuery.data?.history ?? [], [stationDataQuery.data]);
  const imageTimeline = useMemo(() => stationDataQuery.data?.timeline ?? [], [stationDataQuery.data]);

  // ---- Station config (owner-only) -------------------------------------------
  const configQuery = useQuery({
    queryKey: stationConfigKey(activeStationId),
    enabled: isAuthenticated && Boolean(activeStationId),
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

  const isStationConfigLoading = isAuthenticated && Boolean(activeStationId) && configQuery.isLoading;
  const configLoadFailed =
    isAuthenticated &&
    Boolean(activeStationId) &&
    (configQuery.isError || (configQuery.isSuccess && configQuery.data === null));
  const stationConfigError =
    saveError ?? (configLoadFailed ? "Unable to load the selected station settings." : null);

  // Seed the editable description draft once per station, when its config loads.
  const draftLoadedForRef = useRef<string | null>(null);
  useEffect(() => {
    if (!isAuthenticated || !activeStationId) {
      draftLoadedForRef.current = null;
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
    setSaveError(null);
    setCurrentImageIndexState(0);
    setIsPlayingState(false);
  }, [activeStationId]);

  // Jump to the newest image whenever a station's timeline (re)loads.
  useEffect(() => {
    const timeline = stationDataQuery.data?.timeline;
    if (timeline) {
      setCurrentImageIndexState(Math.max(timeline.length - 1, 0));
      setIsPlayingState(false);
    }
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
      if (!stationConfig) return;
      const nextConfig: StationConfigResponse = {
        ...stationConfig,
        stationStartTime: nextSchedule.stationStartTime,
        stationStopTime: nextSchedule.stationStopTime,
        useSunriseSunset: nextSchedule.useSunriseSunset,
        captureIntervalMinutes: Number(nextSchedule.captureInterval),
      };
      const ok = await saveConfig(nextConfig, "config");
      if (!ok) setSaveError(GENERIC_SAVE_ERROR);
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
      if (!stationConfig || stationConfig.isPublic === nextIsPublic) return;
      const ok = await saveConfig({ ...stationConfig, isPublic: nextIsPublic }, "config");
      if (!ok) setSaveError("Unable to update station visibility.");
    },
    [saveConfig, stationConfig]
  );

  // ---- Document title --------------------------------------------------------
  useEffect(() => {
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
    pushStationUrl(webcam.id);
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
      pushStationUrl(parsedStation.id);
      setSelectedWebcam(parsedStation);
      return { success: true, stationId: parsedStation.id };
    },
    [apiBaseUrl, isAuthenticated, queryClient]
  );

  const rotateDeviceSecret = useCallback(
    (stationId: string) => rotateStationDeviceSecretRequest(apiBaseUrl, stationId),
    [apiBaseUrl]
  );

  return useMemo(
    () => ({
      activeWebcam,
      setActiveWebcam,
      webcamList,
      historicalData,
      imageTimeline,
      currentImageIndex,
      setCurrentImageIndex,
      refreshImageTimeline,
      createStation,
      rotateDeviceSecret,
      isPlaying,
      setIsPlaying,
      timezones: TIMEZONES,
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
    }),
    [
      activeWebcam,
      createStation,
      currentImageIndex,
      description,
      descriptionDraft,
      descriptionError,
      historicalData,
      imageTimeline,
      isDescriptionSaving,
      isPlaying,
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
      setCurrentImageIndex,
      setDraftDescription,
      setIsPlaying,
      setIsPublic,
      stationConfigError,
      webcamList,
    ]
  );
};
