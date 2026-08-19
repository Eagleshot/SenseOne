import { useEffect, useState } from "react";

import { motion } from "framer-motion";
import { BookOpen, Settings } from "lucide-react";

import { Accordion } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/Toaster";
import { usePreferences, useStationData } from "@/contexts/AppContext";
import {
  CUSTOM_CAPTURE_INTERVAL_VALUE,
  getCaptureIntervalSelection,
  getCustomCaptureIntervalInput,
  normalizeCaptureInterval,
  validateCaptureInterval,
} from "@/lib/captureInterval";
import { utcTimeOfDayToZoned, zonedTimeOfDayToUtc } from "@/lib/datetime";
import {
  DangerZoneSection,
  ScheduleSettingsSection,
  ThemeSection,
  VisibilitySection,
} from "./WebsiteSettingsSections";

export const WebsiteSettingsPanel: React.FC = () => {
  const { colorTheme, setColorTheme, timezone } = usePreferences();
  const {
    activeWebcam,
    stationStartTime,
    stationStopTime,
    useSunriseSunset,
    captureInterval,
    saveStationSchedule,
    deleteStation,
    rotateDeviceSecret,
    isStationConfigLoading,
    isStationConfigSaving,
    stationConfigError,
    isPublic,
    setIsPublic,
    canEdit,
  } = useStationData();
  const { showToast } = useToast();

  const [isDeleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const isPrivate = !isPublic;

  const [intervalSelection, setIntervalSelection] = useState(() => getCaptureIntervalSelection(captureInterval));
  const [customIntervalInput, setCustomIntervalInput] = useState(() => getCustomCaptureIntervalInput(captureInterval));
  const [intervalError, setIntervalError] = useState<string | null>(() =>
    getCaptureIntervalSelection(captureInterval) === CUSTOM_CAPTURE_INTERVAL_VALUE
      ? validateCaptureInterval(captureInterval)
      : null
  );

  // Config start/stop times are stored and sent to the device in UTC; the
  // panel displays and edits them in the effective display timezone.
  const localStationStartTime = utcTimeOfDayToZoned(stationStartTime, timezone);
  const localStationStopTime = utcTimeOfDayToZoned(stationStopTime, timezone);

  const [draftStationStartTime, setDraftStationStartTime] = useState(localStationStartTime);
  const [draftStationStopTime, setDraftStationStopTime] = useState(localStationStopTime);
  const [draftUseSunriseSunset, setDraftUseSunriseSunset] = useState(useSunriseSunset);
  const [draftCaptureInterval, setDraftCaptureInterval] = useState(captureInterval);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

  useEffect(() => {
    const nextSelection = getCaptureIntervalSelection(captureInterval);
    const nextCustomInput = getCustomCaptureIntervalInput(captureInterval);

    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: re-derive interval controls from the saved config
    setIntervalSelection(nextSelection);
    setCustomIntervalInput(nextCustomInput);
    setIntervalError(
      nextSelection === CUSTOM_CAPTURE_INTERVAL_VALUE ? validateCaptureInterval(captureInterval) : null
    );
  }, [captureInterval]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: re-seed schedule drafts from the saved config
    setDraftStationStartTime(localStationStartTime);
    setDraftStationStopTime(localStationStopTime);
    setDraftUseSunriseSunset(useSunriseSunset);
    setDraftCaptureInterval(captureInterval);
    setScheduleError(null);
  }, [localStationStartTime, localStationStopTime, useSunriseSunset, captureInterval]);

  // Clear delete-state when the station changes (incl. right after a deletion,
  // when the selection moves to the next station).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: reset delete dialog/error per station
    setDeleteDialogOpen(false);
    setDeleteError(null);
  }, [activeWebcam.id]);

  const scheduleControlsDisabled = isStationConfigLoading;

  const handleToggleVisibility = (nextPrivate: boolean) => {
    void (async () => {
      const saved = await setIsPublic(!nextPrivate);
      if (saved) showToast(nextPrivate ? "Station is now private." : "Station is now public.");
    })();
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    const stationName = activeWebcam.name;
    const result = await deleteStation(activeWebcam.id);
    setIsDeleting(false);
    if (result.success) {
      // The selection has already moved on to another station; acknowledge,
      // since otherwise the page just switching reads like a glitch.
      setDeleteDialogOpen(false);
      showToast(`Station “${stationName}” deleted.`);
    } else {
      setDeleteDialogOpen(false);
      setDeleteError(result.error ?? "Unable to delete the station.");
    }
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
    // The backend stores the window in UTC and requires start < stop there
    // too, so a window that wraps past midnight UTC can't be saved.
    const utcStart = zonedTimeOfDayToUtc(draftStationStartTime, timezone);
    const utcStop = zonedTimeOfDayToUtc(draftStationStopTime, timezone);
    if (utcStart >= utcStop) {
      setScheduleError(
        `In UTC this window is ${utcStart}-${utcStop}, which crosses midnight. Choose times that stay within one UTC day.`
      );
      return false;
    }
    setScheduleError(null);
    return true;
  };

  const handleSaveSchedule = () => {
    if (!validateScheduleTimes()) return;
    void (async () => {
      const saved = await saveStationSchedule({
        stationStartTime: zonedTimeOfDayToUtc(draftStationStartTime, timezone),
        stationStopTime: zonedTimeOfDayToUtc(draftStationStopTime, timezone),
        useSunriseSunset: draftUseSunriseSunset,
        captureInterval: draftCaptureInterval,
      });
      if (saved) showToast("Schedule saved.");
    })();
  };

  const handleCancelScheduleEdit = () => {
    setDraftStationStartTime(localStationStartTime);
    setDraftStationStopTime(localStationStopTime);
    setDraftUseSunriseSunset(useSunriseSunset);
    setDraftCaptureInterval(captureInterval);
    setScheduleError(null);
  };

  const hasScheduleChanges =
    draftStationStartTime !== localStationStartTime ||
    draftStationStopTime !== localStationStopTime ||
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
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-2xl font-bold text-foreground">Settings</h2>
          </div>
          <div className="flex items-center gap-2">
            {activeWebcam.firmwareVersion ? (
              <span className="text-xs text-muted-foreground" title="Firmware version reported by the device">
                Firmware: V{activeWebcam.firmwareVersion}
              </span>
            ) : null}
            <Button asChild variant="outline" size="sm" className="btn-panel">
              <a href="https://api.eagleshot.org/docs" target="_blank" rel="noreferrer">
                <BookOpen className="h-4 w-4" />
                API docs
              </a>
            </Button>
          </div>
        </div>

        <Accordion type="multiple" defaultValue={[]} className="space-y-2">
          {/* Schedule and Visibility edit the station's owner-only config, so
              they're shown only to the owner/admin (canEdit). */}
          {canEdit && (
            <ScheduleSettingsSection
              timezoneLabel={timezone}
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
          )}

          {canEdit && (
            <VisibilitySection
              isPrivate={isPrivate}
              handleToggleVisibility={handleToggleVisibility}
              isStationConfigLoading={isStationConfigLoading}
              isStationConfigSaving={isStationConfigSaving}
            />
          )}

          <ThemeSection colorTheme={colorTheme} setColorTheme={setColorTheme} />

          {canEdit && (
            <DangerZoneSection
              // Remount per station so the rotation dialog's local state
              // (incl. a displayed one-time secret) can't leak across stations.
              key={activeWebcam.id}
              stationId={activeWebcam.id}
              stationName={activeWebcam.name}
              isDeleteDialogOpen={isDeleteDialogOpen}
              setDeleteDialogOpen={setDeleteDialogOpen}
              isDeleting={isDeleting}
              deleteError={deleteError}
              handleConfirmDelete={() => void handleConfirmDelete()}
              onRotateSecret={() => rotateDeviceSecret(activeWebcam.id)}
            />
          )}
        </Accordion>
      </div>
    </motion.div>
  );
};

