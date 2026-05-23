import { Check, Lock, Save, Trash2, Unlock, Upload, X } from "lucide-react";
import type { RefObject } from "react";

import { AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { ColorThemeKey, ColorThemePresetKey } from "@/lib/appThemes";
import { colorThemePresets } from "@/lib/appThemes";
import { CAPTURE_INTERVAL_OPTIONS, CUSTOM_CAPTURE_INTERVAL_VALUE } from "@/lib/captureInterval";
import { cn } from "@/lib/utils";

type ScheduleSettingsSectionProps = {
  stationConfigError: string | null;
  isStationConfigLoading: boolean;
  isStationConfigSaving: boolean;
  scheduleControlsDisabled: boolean;
  draftUseSunriseSunset: boolean;
  setDraftUseSunriseSunset: (value: boolean) => void;
  draftCameraStartTime: string;
  setDraftCameraStartTime: (value: string) => void;
  draftCameraStopTime: string;
  setDraftCameraStopTime: (value: string) => void;
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
  stationConfigError,
  isStationConfigLoading,
  isStationConfigSaving,
  scheduleControlsDisabled,
  draftUseSunriseSunset,
  setDraftUseSunriseSunset,
  draftCameraStartTime,
  setDraftCameraStartTime,
  draftCameraStopTime,
  setDraftCameraStopTime,
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
  <AccordionItem value="camera-schedule" className="rounded-xl border border-border bg-transparent">
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
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-foreground">Use sunrise/sunset</p>
            <p className="text-xs text-muted-foreground">
              Automatically align start and stop with daylight hours.
            </p>
          </div>
          <Switch
            checked={draftUseSunriseSunset}
            onCheckedChange={setDraftUseSunriseSunset}
            disabled={scheduleControlsDisabled}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Start time</label>
            <Input
              type="time"
              value={draftCameraStartTime}
              onChange={(event) => {
                setDraftCameraStartTime(event.target.value);
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
              value={draftCameraStopTime}
              onChange={(event) => {
                setDraftCameraStopTime(event.target.value);
                clearScheduleError();
              }}
              disabled={scheduleControlsDisabled || draftUseSunriseSunset}
              className="h-10"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Capture interval</label>
            <Select value={intervalSelection} onValueChange={handleIntervalSelect} disabled={scheduleControlsDisabled}>
              <SelectTrigger className="bg-background/70 border-border">
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

type ThemeBrandingSectionProps = {
  colorTheme: ColorThemeKey;
  setColorTheme: (theme: ColorThemeKey) => void;
  logoPreviewUrl: string;
  brandLogoUrl: string | null;
  fileInputRef: RefObject<HTMLInputElement | null>;
  handleLogoUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  setBrandLogoUrl: (logoUrl: string | null) => void;
  uploadError: string | null;
};

export const ThemeBrandingSection = ({
  colorTheme,
  setColorTheme,
  logoPreviewUrl,
  brandLogoUrl,
  fileInputRef,
  handleLogoUpload,
  setBrandLogoUrl,
  uploadError,
}: ThemeBrandingSectionProps) => (
  <AccordionItem value="theme" className="rounded-xl border border-border bg-transparent">
    <AccordionTrigger className="px-4 text-sm font-semibold text-foreground hover:no-underline">
      Theme
    </AccordionTrigger>
    <AccordionContent className="px-4 pb-4 pt-0">
      <div className="grid gap-3 sm:grid-cols-3">
        {(Object.entries(colorThemePresets) as Array<[ColorThemePresetKey, (typeof colorThemePresets)[ColorThemePresetKey]]>).map(
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
      <div className="mt-4 flex flex-col gap-4 rounded-xl border border-border bg-[hsl(var(--sidebar-background))]/40 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-border bg-background">
            <img
              src={logoPreviewUrl}
              alt="Current logo"
              className={cn("max-h-12 max-w-12 object-contain", !brandLogoUrl && "dark:invert dark:brightness-0")}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {brandLogoUrl ? "Custom logo uploaded" : "Using default logo"}
            </p>
            <p className="text-xs text-muted-foreground">PNG, JPG, SVG up to 2MB.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Input ref={fileInputRef} type="file" accept="image/*" onChange={handleLogoUpload} className="hidden" />
          <Button type="button" variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="btn-panel">
            <Upload className="h-4 w-4" />
            Upload Logo
          </Button>
          {brandLogoUrl && (
            <Button type="button" variant="outline" size="sm" onClick={() => setBrandLogoUrl(null)} className="btn-panel">
              <Trash2 className="h-4 w-4" />
              Reset
            </Button>
          )}
        </div>
      </div>
      {uploadError && <p className="mt-2 text-xs text-destructive">{uploadError}</p>}
    </AccordionContent>
  </AccordionItem>
);
