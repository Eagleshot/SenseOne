import React, { useEffect, useRef, useState } from 'react';

import { motion } from 'framer-motion';
import { Check, Settings, Trash2, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';

import { useApp } from '@/contexts/AppContext';
import { ColorThemeKey, ColorThemePresetKey, colorThemePresets } from '@/lib/appThemes';
import { cn } from '@/lib/utils';

const INTERVAL_OPTIONS = [
  { value: '5', label: '5 min' },
  { value: '10', label: '10 min' },
  { value: '15', label: '15 min' },
  { value: '30', label: '30 min' },
  { value: '60', label: '60 min' },
] as const;
const INTERVAL_PRESET_VALUES = new Set(INTERVAL_OPTIONS.map((option) => option.value));

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
  } = useApp();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const logoPreviewUrl = brandLogoUrl || '/logo.png';
  const isPresetInterval = INTERVAL_PRESET_VALUES.has(captureInterval);
  const [intervalSelection, setIntervalSelection] = useState(() =>
    isPresetInterval ? captureInterval : 'custom'
  );
  const [customIntervalInput, setCustomIntervalInput] = useState(() => (isPresetInterval ? '' : captureInterval));
  const [intervalError, setIntervalError] = useState<string | null>(null);

  useEffect(() => {
    if (intervalSelection === 'custom') {
      if (!isPresetInterval) {
        setCustomIntervalInput(captureInterval);
      }
      const numeric = Number(captureInterval);
      if (!Number.isInteger(numeric) || numeric < 1 || numeric > 1440) {
        setIntervalError('Interval must be an integer between 1 and 1440 minutes.');
      } else {
        setIntervalError(null);
      }
      return;
    }
    setCustomIntervalInput('');
    setIntervalError(null);
    const nextSelection = isPresetInterval ? captureInterval : 'custom';
    if (nextSelection !== intervalSelection) {
      setIntervalSelection(nextSelection);
    }
  }, [captureInterval, isPresetInterval, intervalSelection]);

  const handleIntervalSelect = (value: string) => {
    if (value === 'custom') {
      setIntervalSelection('custom');
      setCustomIntervalInput(captureInterval);
      setIntervalError(null);
      return;
    }
    setIntervalSelection(value);
    setIntervalError(null);
    setCaptureInterval(value);
  };

  const handleCustomIntervalChange = (value: string) => {
    setCustomIntervalInput(value);
    if (!value.trim()) {
      setIntervalError('Enter a custom interval in minutes.');
      return;
    }
    const numeric = Number(value);
    if (!Number.isInteger(numeric) || numeric < 1 || numeric > 1440) {
      setIntervalError('Interval must be an integer between 1 and 1440 minutes.');
      return;
    }
    setIntervalError(null);
    setCaptureInterval(String(numeric));
  };

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
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Use sunrise/sunset</p>
                    <p className="text-xs text-muted-foreground">
                      Automatically align start and stop with daylight hours.
                    </p>
                  </div>
                  <Switch checked={useSunriseSunset} onCheckedChange={setUseSunriseSunset} />
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Start time</label>
                    <Input
                      type="time"
                      value={cameraStartTime}
                      onChange={(event) => setCameraStartTime(event.target.value)}
                      disabled={useSunriseSunset}
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Stop time</label>
                    <Input
                      type="time"
                      value={cameraStopTime}
                      onChange={(event) => setCameraStopTime(event.target.value)}
                      disabled={useSunriseSunset}
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-muted-foreground">Capture interval</label>
                    <Select value={intervalSelection} onValueChange={handleIntervalSelect}>
                      <SelectTrigger className="bg-background/70 border-border">
                        <SelectValue placeholder="Select interval" />
                      </SelectTrigger>
                      <SelectContent>
                        {INTERVAL_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {intervalSelection === 'custom' && (
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
                      className="h-10"
                    />
                  </div>
                )}
                {intervalError && <p className="text-xs text-destructive">{intervalError}</p>}
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
                        'rounded-xl border p-3 text-left transition-all',
                        colorTheme === themeKey
                          ? 'border-primary bg-primary/5 shadow-soft-md'
                          : 'border-border bg-[hsl(var(--sidebar-background))]/40 hover:border-primary/40'
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

