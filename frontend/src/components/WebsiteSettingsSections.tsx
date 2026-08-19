import { AlertTriangle, Check, KeyRound, Lock, Save, Sunrise, Trash2, Unlock, X } from "lucide-react";
import { useRef, useState } from "react";

import { ProvisioningValue } from "@/components/CreateStationDialog";
import { AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { ColorThemeKey } from "@/lib/appThemes";
import { colorThemePresets } from "@/lib/appThemes";
import { CAPTURE_INTERVAL_OPTIONS, CUSTOM_CAPTURE_INTERVAL_VALUE } from "@/lib/captureInterval";
import { cn } from "@/lib/utils";

type ScheduleSettingsSectionProps = {
  /** Effective IANA display timezone the start/stop times are entered in. */
  timezoneLabel: string;
  stationConfigError: string | null;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
  scheduleControlsDisabled: boolean;
  draftUseSunriseSunset: boolean;
  setDraftUseSunriseSunset: (value: boolean) => void;
  draftStationStartTime: string;
  setDraftStationStartTime: (value: string) => void;
  draftStationStopTime: string;
  setDraftStationStopTime: (value: string) => void;
  intervalSelection: string;
  handleIntervalSelect: (value: string) => void;
  customIntervalInput: string;
  handleCustomIntervalChange: (value: string) => void;
  intervalError: string | null;
  scheduleError: string | null;
  clearScheduleError: () => void;
  handleCancelScheduleEdit: () => void;
  handleSaveSchedule: () => void;
  isButtonDisabled: boolean;
};

export const ScheduleSettingsSection = ({
  timezoneLabel,
  stationConfigError,
  isStationConfigLoading,
  isStationConfigSaving,
  scheduleControlsDisabled,
  draftUseSunriseSunset,
  setDraftUseSunriseSunset,
  draftStationStartTime,
  setDraftStationStartTime,
  draftStationStopTime,
  setDraftStationStopTime,
  intervalSelection,
  handleIntervalSelect,
  customIntervalInput,
  handleCustomIntervalChange,
  intervalError,
  scheduleError,
  clearScheduleError,
  handleCancelScheduleEdit,
  handleSaveSchedule,
  isButtonDisabled,
}: ScheduleSettingsSectionProps) => (
  <AccordionItem value="station-schedule" className="rounded-xl border border-border bg-transparent">
    <AccordionTrigger className="px-4 text-sm font-semibold text-foreground hover:no-underline">
      Schedule
    </AccordionTrigger>
    <AccordionContent className="px-4 pb-4 pt-0">
      <div className="space-y-4 pt-1">
        {(stationConfigError || isStationConfigLoading || isStationConfigSaving) && (
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <p className={cn("font-medium", stationConfigError ? "text-destructive" : "text-muted-foreground")}>
              {stationConfigError
                ? stationConfigError
                : isStationConfigLoading
                  ? "Loading station settings..."
                  : "Saving changes..."}
            </p>
          </div>
        )}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-4">
            <label
              htmlFor="schedule-sunrise-sunset"
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <Sunrise className="h-3.5 w-3.5" />
              Use sunrise/sunset
            </label>
            <Switch
              id="schedule-sunrise-sunset"
              checked={draftUseSunriseSunset}
              onCheckedChange={setDraftUseSunriseSunset}
              disabled={scheduleControlsDisabled}
            />
          </div>
          <p className="pl-5 text-xs text-muted-foreground">
            Automatically align start and stop with daylight hours.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Start time</label>
            <Input
              type="time"
              value={draftStationStartTime}
              onChange={(event) => {
                setDraftStationStartTime(event.target.value);
                clearScheduleError();
              }}
              disabled={scheduleControlsDisabled || draftUseSunriseSunset}
              className="h-10"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Stop time</label>
            <Input
              type="time"
              value={draftStationStopTime}
              onChange={(event) => {
                setDraftStationStopTime(event.target.value);
                clearScheduleError();
              }}
              disabled={scheduleControlsDisabled || draftUseSunriseSunset}
              className="h-10"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Capture interval</label>
            <Select value={intervalSelection} onValueChange={handleIntervalSelect} disabled={scheduleControlsDisabled}>
              <SelectTrigger className="bg-background/70">
                <SelectValue placeholder="Select interval" />
              </SelectTrigger>
              <SelectContent>
                {CAPTURE_INTERVAL_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
                <SelectItem value={CUSTOM_CAPTURE_INTERVAL_VALUE}>Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Start and stop times are in {timezoneLabel} (the selected display timezone) and stored in UTC.
        </p>
        {intervalSelection === CUSTOM_CAPTURE_INTERVAL_VALUE && (
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Custom interval (minutes)</label>
            <Input
              type="number"
              inputMode="numeric"
              min={1}
              max={1440}
              step={1}
              value={customIntervalInput}
              onChange={(event) => handleCustomIntervalChange(event.target.value)}
              disabled={scheduleControlsDisabled}
              className="h-10"
            />
          </div>
        )}
        {intervalError && <p className="text-xs text-destructive">{intervalError}</p>}
        {scheduleError && <p className="text-xs text-destructive">{scheduleError}</p>}
        <div className="flex gap-2 pt-2 justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCancelScheduleEdit}
            disabled={isButtonDisabled}
            className="btn-panel"
          >
            <X className="h-4 w-4" />
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleSaveSchedule}
            disabled={isButtonDisabled}
            className="btn-panel"
          >
            <Save className="h-4 w-4" />
            Save Schedule
          </Button>
        </div>
      </div>
    </AccordionContent>
  </AccordionItem>
);

type VisibilitySectionProps = {
  isPrivate: boolean;
  handleToggleVisibility: (nextPrivate: boolean) => void;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
};

export const VisibilitySection = ({
  isPrivate,
  handleToggleVisibility,
  isStationConfigLoading,
  isStationConfigSaving,
}: VisibilitySectionProps) => (
  <AccordionItem value="access" className="rounded-xl border border-border bg-transparent">
    <AccordionTrigger className="px-4 text-sm font-semibold text-foreground hover:no-underline">
      Visibility
    </AccordionTrigger>
    <AccordionContent className="px-4 pb-4 pt-0">
      <div className="flex items-start justify-between gap-4 pt-1">
        <div>
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            {isPrivate ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
            {isPrivate ? "Private station" : "Public station"}
          </p>
          <p className="text-xs text-muted-foreground">
            {isPrivate
              ? "Only you and admins can see this station and its data."
              : "Anyone can view this station, its images, history, and weather."}
          </p>
        </div>
        <Switch
          checked={isPrivate}
          onCheckedChange={handleToggleVisibility}
          disabled={isStationConfigLoading || isStationConfigSaving}
        />
      </div>
    </AccordionContent>
  </AccordionItem>
);

type DangerZoneSectionProps = {
  stationId: string;
  stationName: string;
  isDeleteDialogOpen: boolean;
  setDeleteDialogOpen: (open: boolean) => void;
  isDeleting: boolean;
  deleteError: string | null;
  handleConfirmDelete: () => void;
  onRotateSecret: () => Promise<{ success: boolean; secret?: string; error?: string }>;
};

export const DangerZoneSection = ({
  stationId,
  stationName,
  isDeleteDialogOpen,
  setDeleteDialogOpen,
  isDeleting,
  deleteError,
  handleConfirmDelete,
  onRotateSecret,
}: DangerZoneSectionProps) => {
  // Secret-rotation state is local; the panel remounts this section per
  // station (key), so it can't leak across stations.
  const [isRotateDialogOpen, setRotateDialogOpen] = useState(false);
  const [isRotating, setIsRotating] = useState(false);
  const [rotatedSecret, setRotatedSecret] = useState<string | null>(null);
  const [rotateError, setRotateError] = useState<string | null>(null);
  const [secretCopied, setSecretCopied] = useState(false);
  const copyResetRef = useRef<number | undefined>(undefined);

  const handleRotateDialogChange = (open: boolean) => {
    if (isRotating) return;
    // While the one-time secret is on screen, only the Done button closes.
    if (!open && rotatedSecret) return;
    setRotateDialogOpen(open);
    if (!open) setRotateError(null);
  };

  const handleRotateDone = () => {
    setRotateDialogOpen(false);
    setRotatedSecret(null);
    setSecretCopied(false);
  };

  const handleConfirmRotate = async () => {
    setIsRotating(true);
    setRotateError(null);
    const result = await onRotateSecret();
    setIsRotating(false);
    if (result.success && result.secret) {
      setRotatedSecret(result.secret);
    } else {
      setRotateError(result.error ?? "Unable to rotate the device secret.");
    }
  };

  const handleCopySecret = async () => {
    if (!rotatedSecret) return;
    try {
      await navigator.clipboard.writeText(rotatedSecret);
      setSecretCopied(true);
      window.clearTimeout(copyResetRef.current);
      copyResetRef.current = window.setTimeout(() => setSecretCopied(false), 2000);
    } catch {
      // Clipboard unavailable; the value is still selectable in the field.
    }
  };

  return (
  <AccordionItem value="danger-zone" className="rounded-xl border border-destructive/40 bg-transparent">
    <AccordionTrigger className="px-4 text-sm font-semibold text-destructive hover:no-underline">
      Danger zone
    </AccordionTrigger>
    <AccordionContent className="px-4 pb-4 pt-0">
      <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">Rotate device secret</p>
          <p className="text-xs text-muted-foreground">
            Mints a new signing secret and invalidates the current one immediately — the device
            stops working until it is re-flashed with the new secret.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setRotateDialogOpen(true)}
          className="btn-panel shrink-0"
        >
          <KeyRound className="h-4 w-4" />
          Rotate secret
        </Button>
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-border/60 pt-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">Delete this station</p>
          <p className="text-xs text-muted-foreground">
            Permanently removes the station, its images, and all sensor history. This cannot be undone.
          </p>
        </div>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          onClick={() => setDeleteDialogOpen(true)}
          className="shrink-0"
        >
          <Trash2 className="h-4 w-4" />
          Delete station
        </Button>
      </div>
      {deleteError && (
        <p role="alert" className="pt-2 text-xs text-destructive">
          {deleteError}
        </p>
      )}

      <Dialog open={isRotateDialogOpen} onOpenChange={handleRotateDialogChange}>
        <DialogContent
          className="max-w-md"
          hideCloseButton={Boolean(rotatedSecret)}
          onInteractOutside={(event) => rotatedSecret && event.preventDefault()}
          onEscapeKeyDown={(event) => rotatedSecret && event.preventDefault()}
        >
          {rotatedSecret ? (
            <div className="space-y-4">
              <DialogHeader>
                <DialogTitle>New device secret</DialogTitle>
                <DialogDescription>
                  Flash this into the device firmware (with the unchanged station ID below).
                </DialogDescription>
              </DialogHeader>
              <ProvisioningValue
                id="rotated-station-id"
                label="Station ID (unchanged)"
                hint="STATION_ID stays the same — only the secret rotated."
                value={stationId}
                copied={false}
                onCopy={() => void navigator.clipboard.writeText(stationId).catch(() => {})}
              />
              <ProvisioningValue
                id="rotated-station-secret"
                label="Device secret"
                hint="Set STATION_SECRET_B64 to this value."
                value={rotatedSecret}
                copied={secretCopied}
                onCopy={() => void handleCopySecret()}
              />
              <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                <p className="text-xs text-foreground">
                  This secret is shown <span className="font-semibold">only once</span>. The old
                  secret no longer works.
                </p>
              </div>
              <DialogFooter>
                <Button type="button" onClick={handleRotateDone}>
                  Done
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4">
              <DialogHeader>
                <DialogTitle>Rotate the device secret for “{stationName}”?</DialogTitle>
                <DialogDescription>
                  The current secret stops working <span className="font-semibold">immediately</span>:
                  the device will fail to upload until it is re-flashed with the new secret. Rotate
                  if the secret leaked or the device is being replaced.
                </DialogDescription>
              </DialogHeader>
              {rotateError && (
                <p role="alert" className="text-sm text-destructive">
                  {rotateError}
                </p>
              )}
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleRotateDialogChange(false)}
                  disabled={isRotating}
                  className="btn-panel"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => void handleConfirmRotate()}
                  disabled={isRotating}
                >
                  <KeyRound className="h-4 w-4" />
                  {isRotating ? "Rotating..." : "Rotate now"}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={isDeleteDialogOpen} onOpenChange={(open) => !isDeleting && setDeleteDialogOpen(open)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete “{stationName}”?</DialogTitle>
            <DialogDescription>
              This permanently deletes the station, every stored image, and its entire sensor
              history. A device still flashed with this station&apos;s secret will stop working.{" "}
              <span className="font-semibold text-destructive">This cannot be undone.</span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
              className="btn-panel"
            >
              Cancel
            </Button>
            <Button type="button" variant="destructive" onClick={handleConfirmDelete} disabled={isDeleting}>
              <Trash2 className="h-4 w-4" />
              {isDeleting ? "Deleting..." : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AccordionContent>
  </AccordionItem>
  );
};

type ThemeSectionProps = {
  colorTheme: ColorThemeKey;
  setColorTheme: (theme: ColorThemeKey) => void;
};

export const ThemeSection = ({
  colorTheme,
  setColorTheme,
}: ThemeSectionProps) => (
  <AccordionItem value="theme" className="rounded-xl border border-border bg-transparent">
    <AccordionTrigger className="px-4 text-sm font-semibold text-foreground hover:no-underline">
      Theme
    </AccordionTrigger>
    <AccordionContent className="px-4 pb-4 pt-0">
      <div className="grid gap-3 sm:grid-cols-3">
        {(Object.entries(colorThemePresets) as Array<[ColorThemeKey, (typeof colorThemePresets)[ColorThemeKey]]>).map(
          ([themeKey, preset]) => (
            <button
              key={themeKey}
              type="button"
              onClick={() => setColorTheme(themeKey)}
              className={cn("selector-tile p-3 text-left", colorTheme === themeKey ? "border-primary bg-primary/5 shadow-soft-md" : "")}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    {themeKey === "embernova" ? `${preset.label} (default)` : preset.label}
                  </p>
                  <p className="text-xs text-muted-foreground">{preset.description}</p>
                </div>
                {colorTheme === themeKey && <Check className="h-4 w-4 text-primary" />}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: `hsl(${preset.vars.primary})` }} />
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: `hsl(${preset.vars.chart2})` }} />
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: `hsl(${preset.vars.chart3})` }} />
              </div>
            </button>
          )
        )}
      </div>
    </AccordionContent>
  </AccordionItem>
);

