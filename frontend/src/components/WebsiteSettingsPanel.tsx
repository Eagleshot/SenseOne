import { useEffect, useRef, useState } from 'react';

import { motion } from 'framer-motion';
import { Check, Settings, Trash2, Upload, Save, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';

import { useApp } from '@/contexts/useApp';
import { ColorThemePresetKey, colorThemePresets } from '@/lib/appThemes';
import {
  CAPTURE_INTERVAL_OPTIONS,
  CUSTOM_CAPTURE_INTERVAL_VALUE,
  getCaptureIntervalSelection,
  getCustomCaptureIntervalInput,
  normalizeCaptureInterval,
  validateCaptureInterval,
} from '@/lib/captureInterval';
import { cn } from '@/lib/utils';

export const WebsiteSettingsPanel: React.FC = () => {
  const {
    colorTheme,
    setColorTheme,
    brandLogoUrl,
    setBrandLogoUrl,
    cameraStartTime,
    setCameraStartTime,
    cameraStopTime,
    setCameraStopTime,
    useSunriseSunset,
    setUseSunriseSunset,
    captureInterval,
    setCaptureInterval,
    isStationConfigLoading,
    isStationConfigSaving,
    stationConfigError,
  } = useApp();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const logoPreviewUrl = brandLogoUrl || '/logo.png';
  const scheduleControlsDisabled = isStationConfigLoading;
  const [intervalSelection, setIntervalSelection] = useState(() => getCaptureIntervalSelection(captureInterval));
  const [customIntervalInput, setCustomIntervalInput] = useState(() => getCustomCaptureIntervalInput(captureInterval));
  const [intervalError, setIntervalError] = useState<string | null>(() =>
    getCaptureIntervalSelection(captureInterval) === CUSTOM_CAPTURE_INTERVAL_VALUE
      ? validateCaptureInterval(captureInterval)
      : null
  );
  
  const [draftCameraStartTime, setDraftCameraStartTime] = useState(cameraStartTime);
  const [draftCameraStopTime, setDraftCameraStopTime] = useState(cameraStopTime);
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

  // Sync draft times when actual times change
  useEffect(() => {
    setDraftCameraStartTime(cameraStartTime);
    setDraftCameraStopTime(cameraStopTime);
    setDraftUseSunriseSunset(useSunriseSunset);
    setDraftCaptureInterval(captureInterval);
    setScheduleError(null);
  }, [cameraStartTime, cameraStopTime, useSunriseSunset, captureInterval]);

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
    const error = validateCaptureInterval(value);
    setIntervalError(error);

    const normalizedValue = normalizeCaptureInterval(value);
    if (!normalizedValue) {
      return;
    }

    setDraftCaptureInterval(normalizedValue);
  };

  const validateScheduleTimes = (): boolean => {
    // String comparison works because HH:MM format is lexicographically ordered
    if (draftCameraStartTime >= draftCameraStopTime) {
      setScheduleError(`Start time (${draftCameraStartTime}) must be earlier than stop time (${draftCameraStopTime})`);
      return false;
    }
    setScheduleError(null);
    return true;
  };

  const handleSaveSchedule = () => {
    if (!validateScheduleTimes()) {
      return;
    }
    setCameraStartTime(draftCameraStartTime);
    setCameraStopTime(draftCameraStopTime);
    setUseSunriseSunset(draftUseSunriseSunset);
    setCaptureInterval(draftCaptureInterval);
  };

  const handleCancelScheduleEdit = () => {
    setDraftCameraStartTime(cameraStartTime);
    setDraftCameraStopTime(cameraStopTime);
    setDraftUseSunriseSunset(useSunriseSunset);
    setDraftCaptureInterval(captureInterval);
    setScheduleError(null);
  };

  const hasScheduleChanges =
    draftCameraStartTime !== cameraStartTime ||
    draftCameraStopTime !== cameraStopTime ||
    draftUseSunriseSunset !== useSunriseSunset ||
    draftCaptureInterval !== captureInterval;

  const isButtonDisabled = scheduleControlsDisabled || isStationConfigSaving || !hasScheduleChanges;

  const handleLogoUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setUploadError('Please upload an image file.');
      event.target.value = '';
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setUploadError('Logo must be 2MB or smaller.');
      event.target.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setBrandLogoUrl(reader.result);
        setUploadError(null);
      }
    };
    reader.onerror = () => setUploadError('Could not read this file. Try another image.');
    reader.readAsDataURL(file);
    event.target.value = '';
  };

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

        <Accordion
          type="multiple"
          defaultValue={['camera-schedule', 'theme']}
          className="space-y-2"
        >
          <AccordionItem value="camera-schedule" className="rounded-xl border border-border bg-transparent">
            <AccordionTrigger className="px-4 text-sm font-semibold text-foreground hover:no-underline">
              Camera Schedule
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4 pt-0">
              <div className="space-y-4 rounded-xl border border-border bg-[hsl(var(--sidebar-background))]/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <p className="text-muted-foreground">These settings are saved to the selected station.</p>
                  <p className={cn('font-medium', stationConfigError ? 'text-destructive' : 'text-muted-foreground')}>
                    {stationConfigError
                      ? stationConfigError
                      : isStationConfigLoading
                        ? 'Loading station settings...'
                        : isStationConfigSaving
                          ? 'Saving changes...'
                          : 'All changes saved.'}
                  </p>
                </div>
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
                      className={cn(
                        'selector-tile p-3 text-left',
                        colorTheme === themeKey
                          ? 'border-primary bg-primary/5 shadow-soft-md'
                          : ''
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-foreground">
                            {themeKey === 'embernova' ? `${preset.label} (default)` : preset.label}
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
                      className={cn('max-h-12 max-w-12 object-contain', !brandLogoUrl && 'dark:invert dark:brightness-0')}
                    />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {brandLogoUrl ? 'Custom logo uploaded' : 'Using default logo'}
                    </p>
                    <p className="text-xs text-muted-foreground">PNG, JPG, SVG up to 2MB.</p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleLogoUpload}
                    className="hidden"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    className="btn-panel"
                  >
                    <Upload className="h-4 w-4" />
                    Upload Logo
                  </Button>
                  {brandLogoUrl && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setBrandLogoUrl(null)}
                      className="btn-panel"
                    >
                      <Trash2 className="h-4 w-4" />
                      Reset
                    </Button>
                  )}
                </div>
              </div>
              {uploadError && <p className="mt-2 text-xs text-destructive">{uploadError}</p>}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
    </motion.div>
  );
};
