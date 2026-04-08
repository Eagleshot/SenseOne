import { useCallback, useEffect, useRef, useState } from "react";

import { SensorData, TimezoneOption, Webcam } from "@/data/types";

import {
  DESCRIPTION_MAX_LENGTH,
  FALLBACK_STATION_SCHEDULE_CONFIG,
  createStationScheduleUpdate,
  StationDetailResponse,
  StationConfigResponse,
  StationScheduleConfig,
  StationSummaryResponse,
  TimelineImage,
  TimelineItemResponse,
  SensorDataResponse,
  createStationConfigRequest,
  FALLBACK_WEBCAM,
  UNAVAILABLE_WEBCAM,
  fetchJson,
  isAbortError,
  parseStationConfigResponse,
  parseStationResponse,
  parseTimestampResponse,
  parseTimelineItemResponse,
  selectActiveWebcam,
} from "./appContextUtils";

export type WebcamDataState = {
  activeWebcam: Webcam;
  setActiveWebcam: (webcam: Webcam) => void;
  webcamList: Webcam[];
  historicalData: SensorData[];
  imageTimeline: TimelineImage[];
  currentImageIndex: number;
  setCurrentImageIndex: (index: number) => void;
  refreshImageTimeline: () => Promise<void>;
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  timezones: TimezoneOption[];
  cameraStartTime: string;
  setCameraStartTime: (time: string) => void;
  cameraStopTime: string;
  setCameraStopTime: (time: string) => void;
  useSunriseSunset: boolean;
  setUseSunriseSunset: (value: boolean) => void;
  captureInterval: string;
  setCaptureInterval: (interval: string) => void;
  description: string;
  descriptionDraft: string;
  setDraftDescription: (description: string) => void;
  saveDescription: () => Promise<boolean>;
  isDescriptionSaving: boolean;
  descriptionError: string | null;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
  stationConfigError: string | null;
};

export const useWebcamData = (apiBaseUrl: string, isAuthenticated: boolean): WebcamDataState => {
  const [webcamList, setWebcamList] = useState<Webcam[]>([]);
  const [activeWebcam, setActiveWebcamState] = useState<Webcam>(FALLBACK_WEBCAM);
  const [historicalData, setHistoricalData] = useState<SensorData[]>([]);
  const [imageTimeline, setImageTimeline] = useState<TimelineImage[]>([]);
  const [currentImageIndex, setCurrentImageIndexState] = useState(0);
  const [isPlaying, setIsPlayingState] = useState(false);
  const [timezones, setTimezones] = useState<TimezoneOption[]>([]);
  const [stationSchedule, setStationSchedule] = useState<StationScheduleConfig>(FALLBACK_STATION_SCHEDULE_CONFIG);
  const [descriptionDraft, setDescriptionDraft] = useState("");
  const [isDescriptionSaving, setIsDescriptionSaving] = useState(false);
  const [descriptionError, setDescriptionError] = useState<string | null>(null);
  const [isStationConfigLoading, setIsStationConfigLoading] = useState(false);
  const [isStationConfigSaving, setIsStationConfigSaving] = useState(false);
  const [stationConfigError, setStationConfigError] = useState<string | null>(null);
  const activeStationIdRef = useRef(activeWebcam.id);
  const stationConfigRef = useRef<StationConfigResponse | null>(null);
  const stationScheduleRef = useRef<StationScheduleConfig>(FALLBACK_STATION_SCHEDULE_CONFIG);
  const stationConfigRequestIdRef = useRef(0);
  const stationConfigSaveIdRef = useRef(0);

  const resetTimelineState = useCallback(() => {
    setHistoricalData([]);
    setImageTimeline([]);
    setCurrentImageIndexState(0);
    setIsPlayingState(false);
  }, []);

  const applyStationConfig = useCallback((config: StationConfigResponse | null) => {
    stationConfigRef.current = config;

    const nextSchedule = config ? parseStationConfigResponse(config) : FALLBACK_STATION_SCHEDULE_CONFIG;
    stationScheduleRef.current = nextSchedule;
    setStationSchedule(nextSchedule);
    setDescriptionDraft(config?.description ?? "");
    setActiveWebcamState((currentValue) =>
      config && currentValue.id === activeStationIdRef.current
        ? { ...currentValue, description: config.description }
        : currentValue
    );
  }, []);

  const resetStationConfigState = useCallback(() => {
    stationConfigRequestIdRef.current += 1;
    stationConfigSaveIdRef.current += 1;
    applyStationConfig(null);
    setIsDescriptionSaving(false);
    setDescriptionError(null);
    setIsStationConfigLoading(false);
    setIsStationConfigSaving(false);
    setStationConfigError(null);
  }, [applyStationConfig]);

  const persistStationConfig = useCallback(
    async (
      nextConfig: StationConfigResponse,
      options: {
        previousConfig: StationConfigResponse;
        onOptimistic?: () => void;
        onRollback?: () => void;
        onSuccess?: (response: StationConfigResponse) => void;
        onError?: () => void;
        onFinally?: () => void;
        setGenericError?: boolean;
        genericErrorMessage?: string;
      } = {}
    ) => {
      const stationId = activeStationIdRef.current;
      const currentConfig = stationConfigRef.current;

      if (!stationId || !isAuthenticated || !currentConfig) {
        return;
      }

      const saveId = stationConfigSaveIdRef.current + 1;
      stationConfigSaveIdRef.current = saveId;
      stationConfigRef.current = nextConfig;
      setIsStationConfigSaving(true);
      if (options.setGenericError) {
        setStationConfigError(null);
      }
      options.onOptimistic?.();

      try {
        const response = await fetchJson<StationConfigResponse>(`${apiBaseUrl}/stations/${encodeURIComponent(stationId)}/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextConfig),
          credentials: "include",
          throwOnHttpError: false,
        });

        if (saveId !== stationConfigSaveIdRef.current || stationId !== activeStationIdRef.current) {
          return;
        }

        if (!response) {
          stationConfigRef.current = options.previousConfig;
          options.onRollback?.();
          if (options.setGenericError) {
            setStationConfigError(options.genericErrorMessage ?? "Unable to save the selected station settings.");
          }
          options.onError?.();
          return;
        }

        applyStationConfig(response);
        options.onSuccess?.(response);
      } catch (error) {
        if (isAbortError(error)) {
          return;
        }

        if (saveId !== stationConfigSaveIdRef.current || stationId !== activeStationIdRef.current) {
          return;
        }

        stationConfigRef.current = options.previousConfig;
        options.onRollback?.();
        if (options.setGenericError) {
          setStationConfigError(options.genericErrorMessage ?? "Unable to save the selected station settings.");
        }
        options.onError?.();
      } finally {
        if (saveId === stationConfigSaveIdRef.current && stationId === activeStationIdRef.current) {
          setIsStationConfigSaving(false);
          options.onFinally?.();
        }
      }
    },
    [apiBaseUrl, applyStationConfig, isAuthenticated]
  );

  const updateStationSchedule = useCallback(
    async (updater: (current: StationScheduleConfig) => StationScheduleConfig) => {
      const currentConfig = stationConfigRef.current;
      const previousSchedule = stationScheduleRef.current;

      if (!currentConfig || !activeStationIdRef.current || !isAuthenticated) {
        return;
      }

      const nextSchedule = updater(previousSchedule);
      const nextConfig = createStationConfigRequest(currentConfig, createStationScheduleUpdate(nextSchedule));

      await persistStationConfig(nextConfig, {
        previousConfig: currentConfig,
        onOptimistic: () => {
          stationScheduleRef.current = nextSchedule;
          setStationSchedule(nextSchedule);
        },
        onRollback: () => {
          stationScheduleRef.current = previousSchedule;
          setStationSchedule(previousSchedule);
        },
        setGenericError: true,
        genericErrorMessage: "Unable to save the selected station settings.",
      });
    },
    [isAuthenticated, persistStationConfig]
  );

  const saveDescription = useCallback(async () => {
    const currentConfig = stationConfigRef.current;
    if (!currentConfig || !activeStationIdRef.current || !isAuthenticated) {
      return false;
    }

    if (descriptionDraft.length > DESCRIPTION_MAX_LENGTH) {
      setDescriptionError(`Description must be ${DESCRIPTION_MAX_LENGTH} characters or fewer.`);
      return false;
    }
    const nextDescription = descriptionDraft.slice(0, DESCRIPTION_MAX_LENGTH);
    const nextConfig = createStationConfigRequest(currentConfig, { description: nextDescription });
    let didSave = false;

    setDescriptionError(null);
    setIsDescriptionSaving(true);

    await persistStationConfig(nextConfig, {
      previousConfig: currentConfig,
      onSuccess: () => {
        setDescriptionDraft(nextDescription);
        didSave = true;
      },
      onRollback: () => {
        setDescriptionDraft(nextDescription);
      },
      onError: () => {
        setDescriptionError("Unable to save the station description.");
        didSave = false;
      },
      onFinally: () => {
        setIsDescriptionSaving(false);
      },
    });

    return didSave;
  }, [descriptionDraft, isAuthenticated, persistStationConfig]);

  useEffect(() => {
    activeStationIdRef.current = activeWebcam.id;
  }, [activeWebcam.id]);

  useEffect(() => {
    const controller = new AbortController();

    const loadPublicData = async () => {
      try {
        const [webcamResponse, timezoneResponse] = await Promise.all([
          fetchJson<StationSummaryResponse[]>(`${apiBaseUrl}/stations`, {
            signal: controller.signal,
            throwOnHttpError: false,
          }),
          fetchJson<TimezoneOption[]>(`${apiBaseUrl}/timezones`, {
            signal: controller.signal,
            throwOnHttpError: false,
          }),
        ]);

        if (controller.signal.aborted) return;

        const parsedWebcams = webcamResponse ? webcamResponse.map(parseStationResponse) : [];
        setWebcamList(parsedWebcams);
        setActiveWebcamState((currentValue) =>
          parsedWebcams.length > 0 ? selectActiveWebcam(parsedWebcams, currentValue.id) : UNAVAILABLE_WEBCAM
        );
        setTimezones(timezoneResponse ?? []);
      } catch (error) {
        if (isAbortError(error)) return;

        setWebcamList([]);
        setActiveWebcamState(UNAVAILABLE_WEBCAM);
        setTimezones([]);
      }
    };

    void loadPublicData();

    return () => {
      controller.abort();
    };
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!isAuthenticated || !activeWebcam.id) {
      resetStationConfigState();
      return;
    }

    const stationId = activeWebcam.id;
    const requestId = stationConfigRequestIdRef.current + 1;
    stationConfigRequestIdRef.current = requestId;
    stationConfigSaveIdRef.current += 1;
    setDescriptionError(null);
    setIsStationConfigLoading(true);
    setIsStationConfigSaving(false);
    setStationConfigError(null);

    const controller = new AbortController();

    const loadStationConfig = async () => {
      try {
        const response = await fetchJson<StationConfigResponse>(`${apiBaseUrl}/stations/${encodeURIComponent(stationId)}/config`, {
          credentials: "include",
          signal: controller.signal,
          throwOnHttpError: false,
        });

        if (
          controller.signal.aborted ||
          requestId !== stationConfigRequestIdRef.current ||
          stationId !== activeStationIdRef.current
        ) {
          return;
        }

        if (!response) {
          applyStationConfig(null);
          setStationConfigError("Unable to load the selected station settings.");
          return;
        }

        applyStationConfig(response);
      } catch (error) {
        if (isAbortError(error)) {
          return;
        }

        if (requestId !== stationConfigRequestIdRef.current || stationId !== activeStationIdRef.current) {
          return;
        }

        applyStationConfig(null);
        setStationConfigError("Unable to load the selected station settings.");
      } finally {
        if (requestId === stationConfigRequestIdRef.current && stationId === activeStationIdRef.current) {
          setIsStationConfigLoading(false);
        }
      }
    };

    void loadStationConfig();

    return () => {
      controller.abort();
    };
  }, [activeWebcam.id, apiBaseUrl, applyStationConfig, isAuthenticated, resetStationConfigState]);

  const fetchActiveCameraData = useCallback(
    async (options: { signal?: AbortSignal } = {}) => {
      const cameraId = activeWebcam.id;
      if (!cameraId) {
        resetTimelineState();
        return;
      }

      const stationPath = `${apiBaseUrl}/stations/${encodeURIComponent(cameraId)}`;
      const detailUrl = stationPath;
      const historyUrl = `${stationPath}/history?hours=24`;
      const timelineUrl = `${stationPath}/timeline?count=48`;
      const { signal } = options;

      try {
        const [detailResponse, historyResponse, timelineResponse] = await Promise.all([
          fetchJson<StationDetailResponse>(detailUrl, { signal, throwOnHttpError: false }),
          fetchJson<SensorDataResponse[]>(historyUrl, { signal, throwOnHttpError: false }),
          fetchJson<TimelineItemResponse[]>(timelineUrl, { signal, throwOnHttpError: false }),
        ]);

        if (signal?.aborted) return;

        if (detailResponse) {
          const parsedDetail = parseStationResponse(detailResponse, apiBaseUrl);
          setActiveWebcamState((currentValue) =>
            currentValue.id === cameraId ? { ...currentValue, ...parsedDetail } : currentValue
          );
        }

        const nextTimeline = timelineResponse
          ? timelineResponse.map((item) => parseTimelineItemResponse(item, apiBaseUrl))
          : [];
        setHistoricalData(historyResponse ? historyResponse.map(parseTimestampResponse) : []);
        setImageTimeline(nextTimeline);
        setCurrentImageIndexState(Math.max(nextTimeline.length - 1, 0));
        setIsPlayingState(false);
      } catch (error) {
        if (isAbortError(error)) return;
        resetTimelineState();
      }
    },
    [activeWebcam.id, apiBaseUrl, resetTimelineState]
  );

  useEffect(() => {
    if (!activeWebcam.id) {
      resetTimelineState();
      return;
    }

    const controller = new AbortController();
    void fetchActiveCameraData({ signal: controller.signal });

    return () => {
      controller.abort();
    };
  }, [activeWebcam.id, fetchActiveCameraData, resetTimelineState]);

  useEffect(() => {
    const title = `${activeWebcam.name} | Eagleshot`;
    document.title = title;

    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) {
      ogTitle.setAttribute("content", title);
    }

    const twitterSite = document.querySelector('meta[name="twitter:site"]');
    if (twitterSite) {
      twitterSite.setAttribute("content", title);
    }
  }, [activeWebcam.name]);

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

    return () => {
      clearInterval(interval);
    };
  }, [imageTimeline.length, isPlaying]);

  return {
    activeWebcam,
    setActiveWebcam: (webcam) => setActiveWebcamState(webcam),
    webcamList,
    historicalData,
    imageTimeline,
    currentImageIndex,
    setCurrentImageIndex: (index) => setCurrentImageIndexState(index),
    refreshImageTimeline: async () => {
      await fetchActiveCameraData();
    },
    isPlaying,
    setIsPlaying: (playing) => setIsPlayingState(playing),
    timezones,
    cameraStartTime: stationSchedule.cameraStartTime,
    setCameraStartTime: (time) => {
      void updateStationSchedule((currentValue) => ({ ...currentValue, cameraStartTime: time }));
    },
    cameraStopTime: stationSchedule.cameraStopTime,
    setCameraStopTime: (time) => {
      void updateStationSchedule((currentValue) => ({ ...currentValue, cameraStopTime: time }));
    },
    useSunriseSunset: stationSchedule.useSunriseSunset,
    setUseSunriseSunset: (value) => {
      void updateStationSchedule((currentValue) => ({ ...currentValue, useSunriseSunset: value }));
    },
    captureInterval: stationSchedule.captureInterval,
    setCaptureInterval: (interval) => {
      void updateStationSchedule((currentValue) => ({ ...currentValue, captureInterval: interval }));
    },
    description: stationConfigRef.current?.description ?? activeWebcam.description ?? "",
    descriptionDraft,
    setDraftDescription: (description) => {
      setDescriptionDraft(description.slice(0, DESCRIPTION_MAX_LENGTH));
      setDescriptionError(null);
    },
    saveDescription,
    isDescriptionSaving,
    descriptionError,
    isStationConfigLoading,
    isStationConfigSaving,
    stationConfigError,
  };
};
