import { useEffect, useRef, useState } from "react";

import { motion } from "framer-motion";
import { Settings } from "lucide-react";

import { Accordion } from "@/components/ui/accordion";
import { useApp } from "@/contexts/AppContext";
import {
  CUSTOM_CAPTURE_INTERVAL_VALUE,
  getCaptureIntervalSelection,
  getCustomCaptureIntervalInput,
  normalizeCaptureInterval,
  validateCaptureInterval,
} from "@/lib/captureInterval";
import {
  ScheduleSettingsSection,
  ThemeBrandingSection,
  VisibilitySection,
} from "./WebsiteSettingsSections";

export const WebsiteSettingsPanel: React.FC = () => {
  const {
    colorTheme,
    setColorTheme,
    brandLogoUrl,
    setBrandLogoUrl,
    stationStartTime,
    stationStopTime,
    useSunriseSunset,
    captureInterval,
    saveStationSchedule,
    isStationConfigLoading,
    isStationConfigSaving,
    stationConfigError,
    isPublic,
    setIsPublic,
    isAuthenticated,
  } = useApp();

  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isPrivate = !isPublic;

  const [intervalSelection, setIntervalSelection] = useState(() => getCaptureIntervalSelection(captureInterval));
  const [customIntervalInput, setCustomIntervalInput] = useState(() => getCustomCaptureIntervalInput(captureInterval));
  const [intervalError, setIntervalError] = useState<string | null>(() =>
    getCaptureIntervalSelection(captureInterval) === CUSTOM_CAPTURE_INTERVAL_VALUE
      ? validateCaptureInterval(captureInterval)
      : null
  );

  const [draftStationStartTime, setDraftStationStartTime] = useState(stationStartTime);
  const [draftStationStopTime, setDraftStationStopTime] = useState(stationStopTime);
  const [draftUseSunriseSunset, setDraftUseSunriseSunset] = useState(useSunriseSunset);
  const [draftCaptureInterval, setDraftCaptureInterval] = useState(captureInterval);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

  useEffect(() => {
    const nextSelection = getCaptureIntervalSelection(captureInterval);
    const nextCustomInput = getCustomCaptureIntervalInput(captureInterval);

    setIntervalSelection(nextSelection);
    setCustomIntervalInput(nextCustomInput);
    setIntervalError(
      nextSelection === CUSTOM_CAPTURE_INTERVAL_VALUE ? validateCaptureInterval(captureInterval) : null
    );
  }, [captureInterval]);

  useEffect(() => {
    setDraftStationStartTime(stationStartTime);
    setDraftStationStopTime(stationStopTime);
    setDraftUseSunriseSunset(useSunriseSunset);
    setDraftCaptureInterval(captureInterval);
    setScheduleError(null);
  }, [stationStartTime, stationStopTime, useSunriseSunset, captureInterval]);

  const scheduleControlsDisabled = isStationConfigLoading;
  const logoPreviewUrl = brandLogoUrl || "/logo.png";

  const handleToggleVisibility = (nextPrivate: boolean) => {
    void setIsPublic(!nextPrivate);
  };

  const clearScheduleError = () => setScheduleError(null);

  const handleIntervalSelect = (value: string) => {
    if (value === CUSTOM_CAPTURE_INTERVAL_VALUE) {
      setIntervalSelection(CUSTOM_CAPTURE_INTERVAL_VALUE);
      setCustomIntervalInput(draftCaptureInterval);
      setIntervalError(null);
      return;
    }
    setIntervalSelection(value);
    setIntervalError(null);
    setDraftCaptureInterval(value);
  };

  const handleCustomIntervalChange = (value: string) => {
    setCustomIntervalInput(value);
    setIntervalError(validateCaptureInterval(value));

    const normalizedValue = normalizeCaptureInterval(value);
    if (normalizedValue) {
      setDraftCaptureInterval(normalizedValue);
    }
  };

  const validateScheduleTimes = (): boolean => {
    if (draftStationStartTime >= draftStationStopTime) {
      setScheduleError(`Start time (${draftStationStartTime}) must be earlier than stop time (${draftStationStopTime})`);
      return false;
    }
    setScheduleError(null);
    return true;
  };

  const handleSaveSchedule = () => {
    if (!validateScheduleTimes()) return;
    void saveStationSchedule({
      stationStartTime: draftStationStartTime,
      stationStopTime: draftStationStopTime,
      useSunriseSunset: draftUseSunriseSunset,
      captureInterval: draftCaptureInterval,
    });
  };

  const handleCancelScheduleEdit = () => {
    setDraftStationStartTime(stationStartTime);
    setDraftStationStopTime(stationStopTime);
    setDraftUseSunriseSunset(useSunriseSunset);
    setDraftCaptureInterval(captureInterval);
    setScheduleError(null);
  };

  const handleLogoUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setUploadError("Please upload an image file.");
      event.target.value = "";
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setUploadError("Logo must be 2MB or smaller.");
      event.target.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setBrandLogoUrl(reader.result);
        setUploadError(null);
      }
    };
    reader.onerror = () => setUploadError("Could not read this file. Try another image.");
    reader.readAsDataURL(file);
    event.target.value = "";
  };

  const hasScheduleChanges =
    draftStationStartTime !== stationStartTime ||
    draftStationStopTime !== stationStopTime ||
    draftUseSunriseSunset !== useSunriseSunset ||
    draftCaptureInterval !== captureInterval;

  const isButtonDisabled = scheduleControlsDisabled || isStationConfigSaving || !hasScheduleChanges;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="panel-shell"
    >
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-2xl font-bold text-foreground">Settings</h2>
        </div>

        <Accordion type="multiple" defaultValue={[]} className="space-y-2">
          <ScheduleSettingsSection
            stationConfigError={stationConfigError}
            isStationConfigLoading={isStationConfigLoading}
            isStationConfigSaving={isStationConfigSaving}
            scheduleControlsDisabled={scheduleControlsDisabled}
            draftUseSunriseSunset={draftUseSunriseSunset}
            setDraftUseSunriseSunset={setDraftUseSunriseSunset}
            draftStationStartTime={draftStationStartTime}
            setDraftStationStartTime={setDraftStationStartTime}
            draftStationStopTime={draftStationStopTime}
            setDraftStationStopTime={setDraftStationStopTime}
            intervalSelection={intervalSelection}
            handleIntervalSelect={handleIntervalSelect}
            customIntervalInput={customIntervalInput}
            handleCustomIntervalChange={handleCustomIntervalChange}
            intervalError={intervalError}
            scheduleError={scheduleError}
            clearScheduleError={clearScheduleError}
            handleCancelScheduleEdit={handleCancelScheduleEdit}
            handleSaveSchedule={handleSaveSchedule}
            isButtonDisabled={isButtonDisabled}
          />

          {isAuthenticated && (
            <VisibilitySection
              isPrivate={isPrivate}
              handleToggleVisibility={handleToggleVisibility}
              isStationConfigLoading={isStationConfigLoading}
              isStationConfigSaving={isStationConfigSaving}
            />
          )}

          <ThemeBrandingSection
            colorTheme={colorTheme}
            setColorTheme={setColorTheme}
            logoPreviewUrl={logoPreviewUrl}
            brandLogoUrl={brandLogoUrl}
            fileInputRef={fileInputRef}
            handleLogoUpload={handleLogoUpload}
            setBrandLogoUrl={setBrandLogoUrl}
            uploadError={uploadError}
          />
        </Accordion>
      </div>
    </motion.div>
  );
};

