import { useMemo, useState } from "react";

import { motion } from "framer-motion";
import { Calendar, Check, ChevronDown, LineChart } from "lucide-react";
import { format } from "date-fns";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";

import { usePreferences, useStationData } from "@/contexts/AppContext";
import {
  createDefaultHistoryDateRange,
  filterHistoricalData,
  HISTORY_RANGE_PRESETS,
  historyTimeRangeForSelection,
  historyWindowHoursForLastHours,
  historyWindowHoursForRange,
} from "@/lib/historyFilters";
import { HistoricalCharts } from "./HistoricalCharts";
import { RawDataTable } from "./RawDataTable";

export const SensorHistoryPanel: React.FC = () => {
  const { historicalData, historicalDataError, setHistoryWindowHours } = useStationData();
  const { timezone } = usePreferences();
  const [dateRange, setDateRange] = useState<DateRange | undefined>(createDefaultHistoryDateRange);
  const [timeFrom, setTimeFrom] = useState("00:00");
  const [timeTo, setTimeTo] = useState("23:59");
  const [draftDateRange, setDraftDateRange] = useState<DateRange | undefined>(dateRange);
  const [draftTimeFrom, setDraftTimeFrom] = useState(timeFrom);
  const [draftTimeTo, setDraftTimeTo] = useState(timeTo);
  // Active "last N hours" preset; null = the custom calendar/time filters
  // apply. Touching any custom control switches back to custom mode.
  const [lastHoursPreset, setLastHoursPreset] = useState<number | null>(null);
  const [isPickerOpen, setPickerOpen] = useState(false);

  const handlePickerOpenChange = (open: boolean) => {
    if (open) {
      setDraftDateRange(dateRange);
      setDraftTimeFrom(timeFrom);
      setDraftTimeTo(timeTo);
    }
    setPickerOpen(open);
  };

  const handlePresetSelect = (hours: number) => {
    setLastHoursPreset(hours);
    setHistoryWindowHours(historyWindowHoursForLastHours(hours));
    setPickerOpen(false);
  };

  // Absolute values are edited as a draft and applied together, avoiding a
  // partially selected range from changing the charts underneath the picker.
  const handleAbsoluteRangeApply = () => {
    if (!draftDateRange?.from || !draftDateRange.to) return;

    setLastHoursPreset(null);
    setDateRange(draftDateRange);
    setTimeFrom(draftTimeFrom);
    setTimeTo(draftTimeTo);
    setHistoryWindowHours(historyWindowHoursForRange(draftDateRange.from));
    setPickerOpen(false);
  };

  const filteredData = useMemo(() => {
    return filterHistoricalData({
      data: historicalData,
      dateRange,
      timeFrom,
      timeTo,
      timezone,
      lastHours: lastHoursPreset ?? undefined,
    });
  }, [historicalData, dateRange, timeFrom, timeTo, timezone, lastHoursPreset]);

  const activePresetLabel = HISTORY_RANGE_PRESETS.find((preset) => preset.hours === lastHoursPreset)?.label;
  const selectedRangeLabel = activePresetLabel
    ? activePresetLabel
    : dateRange?.from && dateRange?.to
      ? `${format(dateRange.from, "MMM d")} - ${format(dateRange.to, "MMM d")}`
      : "Select range";
  const chartTimeRange = historyTimeRangeForSelection({
    dateRange,
    timeFrom,
    timeTo,
    timezone,
    lastHours: lastHoursPreset ?? undefined,
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25 }}
      className="panel-shell"
    >
      <div className="px-4 pt-4 pb-2 sm:px-6 sm:pt-6 sm:pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <LineChart className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-2xl font-bold text-foreground">Data</h2>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Popover open={isPickerOpen} onOpenChange={handlePickerOpenChange}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="btn-panel h-10 min-w-[10.5rem] justify-between rounded-xl px-2.5 data-[state=open]:border-primary/40"
                  aria-label={`Select data range. Current range: ${selectedRangeLabel}`}
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-background/70 shadow-sm">
                      <Calendar className="h-3.5 w-3.5" />
                    </span>
                    <span className="truncate">{selectedRangeLabel}</span>
                  </span>
                  <ChevronDown
                    className={`h-3.5 w-3.5 transition-transform duration-200 ease-out ${isPickerOpen ? "rotate-180" : ""}`}
                  />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                className="w-[min(25rem,calc(100vw-2rem))] overflow-hidden rounded-xl border-sidebar-border/70 p-0 shadow-xl"
                align="end"
                sideOffset={8}
                collisionPadding={16}
              >
                <div className="pointer-events-auto grid sm:grid-cols-[minmax(0,1fr)_8.5rem]">
                  <section className="flex flex-col items-center p-3 sm:p-4" aria-labelledby="absolute-range-label">
                    <p id="absolute-range-label" className="w-full px-1 pb-1 text-sm font-semibold text-foreground">
                      Absolute
                    </p>
                    <CalendarComponent
                      mode="range"
                      defaultMonth={draftDateRange?.from}
                      selected={draftDateRange}
                      onSelect={setDraftDateRange}
                      numberOfMonths={1}
                      showOutsideDays={false}
                      className="mx-auto flex w-fit justify-center px-0 pb-3 pt-2"
                      classNames={{
                        months: "relative flex justify-center",
                        month: "space-y-3",
                        weekday: "w-8 rounded-md text-[0.7rem] font-normal text-muted-foreground",
                        week: "mt-1 flex w-full",
                        day: "relative h-8 w-8 p-0 text-center text-xs focus-within:relative focus-within:z-20 aria-selected:bg-accent first:aria-selected:rounded-l-md last:aria-selected:rounded-r-md",
                        day_button:
                          "inline-flex h-8 w-8 items-center justify-center rounded-md p-0 text-xs font-normal transition-colors hover:bg-accent hover:text-accent-foreground",
                      }}
                      disabled={{ after: new Date() }}
                    />

                    <div className="grid w-full grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-2 border-t border-border pt-3">
                      <label className="min-w-0 space-y-1.5">
                        <span className="block text-[11px] font-medium text-muted-foreground">From time</span>
                        <Input
                          type="time"
                          value={draftTimeFrom}
                          onChange={(event) => setDraftTimeFrom(event.target.value)}
                          className="h-9 w-full rounded-lg bg-background px-2 text-xs"
                        />
                      </label>
                      <span className="flex h-9 items-center text-xs text-muted-foreground" aria-hidden="true">
                        to
                      </span>
                      <label className="min-w-0 space-y-1.5">
                        <span className="block text-[11px] font-medium text-muted-foreground">Until time</span>
                        <Input
                          type="time"
                          value={draftTimeTo}
                          onChange={(event) => setDraftTimeTo(event.target.value)}
                          className="h-9 w-full rounded-lg bg-background px-2 text-xs"
                        />
                      </label>
                    </div>

                    <Button
                      type="button"
                      size="sm"
                      className="mt-3 h-9 w-full rounded-lg"
                      disabled={!draftDateRange?.from || !draftDateRange.to}
                      onClick={handleAbsoluteRangeApply}
                    >
                      Apply range
                    </Button>
                  </section>

                  <section
                    className="order-first border-b border-border bg-sidebar/25 p-3 sm:order-last sm:flex sm:flex-col sm:border-b-0 sm:border-l sm:p-4"
                    aria-labelledby="relative-range-label"
                  >
                    <p id="relative-range-label" className="px-2 pb-2 text-sm font-semibold text-foreground">
                      Relative
                    </p>
                    <div
                      className="grid grid-cols-2 gap-1 sm:flex sm:flex-1 sm:flex-col sm:justify-between sm:gap-0"
                      role="group"
                      aria-label="Relative time ranges"
                    >
                      {HISTORY_RANGE_PRESETS.map((preset) => (
                        <Button
                          key={preset.hours}
                          type="button"
                          variant="ghost"
                          size="sm"
                          className={`h-9 justify-between rounded-md border-l-2 px-2.5 text-xs sm:w-full ${
                            lastHoursPreset === preset.hours
                              ? "border-primary bg-accent text-accent-foreground hover:bg-accent hover:text-accent-foreground"
                              : "border-transparent text-foreground hover:border-primary/40 hover:bg-accent/60 hover:text-foreground"
                          }`}
                          onClick={() => handlePresetSelect(preset.hours)}
                          aria-pressed={lastHoursPreset === preset.hours}
                        >
                          {preset.label}
                          {lastHoursPreset === preset.hours && <Check className="h-3.5 w-3.5" />}
                        </Button>
                      ))}
                    </div>
                  </section>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>

      <div className="space-y-6 px-4 pb-4 pt-0 sm:px-6 sm:pb-6">
        <HistoricalCharts data={filteredData} timeRange={chartTimeRange} loadFailed={historicalDataError} />
        <RawDataTable data={filteredData} />
      </div>
    </motion.div>
  );
};

