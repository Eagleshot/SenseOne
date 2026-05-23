import { useCallback, useEffect, useRef, useState } from "react";

import { TIMEZONES } from "@/data/timezones";
import { SensorData, Webcam } from "@/data/types";
import {
  createStationConfigRequest,
  createStationScheduleUpdate,
  DESCRIPTION_MAX_LENGTH,
  FALLBACK_STATION_SCHEDULE_CONFIG,
  FALLBACK_WEBCAM,
  getStationConfig,
  getStationDetail,
  getStationImageCaptures,
  getStationSensorReadings,
  listStations,
  parseStationConfigResponse,
  parseStationResponse,
  parseTimestampResponse,
  parseTimelineItemResponse,
  selectActiveWebcam,
  StationConfigResponse,
  StationScheduleConfig,
  TimelineImage,
  UNAVAILABLE_WEBCAM,
  updateStationConfig,
} from "@/api/stations";
import { isAbortError } from "@/lib/apiClient";

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
  timezones: typeof TIMEZONES;
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
  isPublic: boolean;
  setIsPublic: (isPublic: boolean) => Promise<void>;
};

export const useWebcamData = (apiBaseUrl: string, isAuthenticated: boolean): WebcamDataState => {
  const [webcamList, setWebcamList] = useState<Webcam[]>([]);
  const [activeWebcam, setActiveWebcamState] = useState<Webcam>(FALLBACK_WEBCAM);
  const [historicalData, setHistoricalData] = useState<SensorData[]>([]);
  const [imageTimeline, setImageTimeline] = useState<TimelineImage[]>([]);
  const [currentImageIndex, setCurrentImageIndexState] = useState(0);
  const [isPlaying, setIsPlayingState] = useState(false);
  const timezones = TIMEZONES;
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
  const cameraDataRequestIdRef = useRef(0);
  const cameraDataAbortRef = useRef<AbortController | null>(null);

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
        const response = await updateStationConfig(apiBaseUrl, stationId, nextConfig);

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

  const setIsPublic = useCallback(
    async (isPublic: boolean) => {
      const currentConfig = stationConfigRef.current;
      if (!currentConfig || !activeStationIdRef.current || !isAuthenticated) {
        return;
      }
      if (currentConfig.isPublic === isPublic) {
        return;
      }
      const nextConfig = createStationConfigRequest(currentConfig, { isPublic });
      const stationId = activeStationIdRef.current;
      await persistStationConfig(nextConfig, {
        previousConfig: currentConfig,
        onSuccess: () => {
          setWebcamList((list) =>
            list.map((webcam) => (webcam.id === stationId ? { ...webcam, isPublic } : webcam))
          );
          setActiveWebcamState((current) =>
            current.id === stationId ? { ...current, isPublic } : current
          );
        },
        setGenericError: true,
        genericErrorMessage: "Unable to update station visibility.",
      });
    },
    [isAuthenticated, persistStationConfig]
  );

  useEffect(() => {
    activeStationIdRef.current = activeWebcam.id;
  }, [activeWebcam.id]);

  useEffect(() => {
    const controller = new AbortController();

    const loadPublicData = async () => {
      try {
        const webcamResponse = await listStations(apiBaseUrl, controller.signal);

        if (controller.signal.aborted) return;

        const parsedWebcams = webcamResponse ? webcamResponse.map(parseStationResponse) : [];
        setWebcamList(parsedWebcams);
        setActiveWebcamState((currentValue) =>
          parsedWebcams.length > 0 ? selectActiveWebcam(parsedWebcams, currentValue.id) : UNAVAILABLE_WEBCAM
        );
      } catch (error) {
        if (isAbortError(error)) return;

        setWebcamList([]);
        setActiveWebcamState(UNAVAILABLE_WEBCAM);
      }
    };

    void loadPublicData();

    return () => {
      controller.abort();
    };
  }, [apiBaseUrl, isAuthenticated]);

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
        const response = await getStationConfig(apiBaseUrl, stationId, controller.signal);

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

  const fetchActiveCameraData = useCallback(async () => {
    const cameraId = activeStationIdRef.current;
    if (!cameraId) {
      resetTimelineState();
      return;
    }

    cameraDataAbortRef.current?.abort();
    const controller = new AbortController();
    cameraDataAbortRef.current = controller;
    const requestId = cameraDataRequestIdRef.current + 1;
    cameraDataRequestIdRef.current = requestId;

    const { signal } = controller;

    const isStale = () =>
      requestId !== cameraDataRequestIdRef.current ||
      cameraId !== activeStationIdRef.current ||
      signal.aborted;

    try {
      const [detailResponse, historyResponse, timelineResponse] = await Promise.all([
        getStationDetail(apiBaseUrl, cameraId, signal),
        getStationSensorReadings(apiBaseUrl, cameraId, 24, signal),
        getStationImageCaptures(apiBaseUrl, cameraId, 48, signal),
      ]);

      if (isStale()) return;

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
      if (isAbortError(error) || isStale()) return;
      resetTimelineState();
    }
  }, [apiBaseUrl, resetTimelineState]);

  useEffect(() => {
    if (!activeWebcam.id) {
      resetTimelineState();
      return;
    }

    void fetchActiveCameraData();

    return () => {
      cameraDataAbortRef.current?.abort();
      cameraDataAbortRef.current = null;
    };
  }, [activeWebcam.id, fetchActiveCameraData, isAuthenticated, resetTimelineState]);

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
    refreshImageTimeline: fetchActiveCameraData,
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
    isPublic: stationConfigRef.current?.isPublic ?? activeWebcam.isPublic ?? true,
    setIsPublic,
  };
};
