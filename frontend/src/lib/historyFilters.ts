import type { DateRange } from "react-day-picker";

import { SensorData } from "@/data/types";
import { zonedDateTimeToInstant } from "@/lib/datetime";

const DAY_IN_MS = 24 * 60 * 60 * 1000;

// Relative presets are limited to one rolling year. Absolute ranges may
// request any past date stored for the station.
export const DEFAULT_HISTORY_HOURS = 24;
export const MAX_HISTORY_HOURS = 365 * 24;

/** Backend fetch window (in hours back from now) needed to cover a picked
 * range: from the start of the range's first day, never below the default (so
 * the latest-reading consumers always have the most recent day). */
export const historyWindowHoursForRange = (from: Date | undefined, now: Date = new Date()): number => {
  if (!from) return DEFAULT_HISTORY_HOURS;
  const startOfFromDay = new Date(from);
  startOfFromDay.setHours(0, 0, 0, 0);
  const hours = Math.ceil((now.getTime() - startOfFromDay.getTime()) / (60 * 60 * 1000));
  return Math.max(DEFAULT_HISTORY_HOURS, hours);
};

/** Quick rolling-window presets in the range picker; the calendar plus the
 * time inputs remain the unrestricted absolute alternative. */
export const HISTORY_RANGE_PRESETS: ReadonlyArray<{ label: string; hours: number }> = [
  { label: "Last 1 h", hours: 1 },
  { label: "Last 6 h", hours: 6 },
  { label: "Last 24 h", hours: 24 },
  { label: "Last 3 days", hours: 3 * 24 },
  { label: "Last 7 days", hours: 7 * 24 },
  { label: "Last 30 days", hours: 30 * 24 },
  { label: "Last 90 days", hours: 90 * 24 },
  { label: "Last 6 months", hours: 182 * 24 },
  { label: "Last year", hours: MAX_HISTORY_HOURS },
];

/** Backend fetch window covering a "last N hours" preset. Short presets keep
 * the default fetch, while quick ranges remain bounded to the largest preset. */
export const historyWindowHoursForLastHours = (hours: number): number =>
  Math.min(MAX_HISTORY_HOURS, Math.max(DEFAULT_HISTORY_HOURS, Math.ceil(hours)));

export type HistoryTimeRange = readonly [start: number, end: number];

type HistoryTimeRangeOptions = {
  dateRange?: DateRange;
  timeFrom: string;
  timeTo: string;
  timezone: string;
  lastHours?: number;
  now?: Date;
};

/** Exact x-axis domain represented by the active relative or absolute picker
 * selection. The end minute is inclusive, matching filterHistoricalData. */
export const historyTimeRangeForSelection = ({
  dateRange,
  timeFrom,
  timeTo,
  timezone,
  lastHours,
  now = new Date(),
}: HistoryTimeRangeOptions): HistoryTimeRange => {
  if (lastHours !== undefined) {
    return [now.getTime() - lastHours * 60 * 60 * 1000, now.getTime()];
  }

  if (!dateRange?.from) {
    return [now.getTime() - DEFAULT_HISTORY_HOURS * 60 * 60 * 1000, now.getTime()];
  }

  const start = zonedDateTimeToInstant(dateRange.from, timeFrom, timezone).getTime();
  let end = zonedDateTimeToInstant(dateRange.to ?? dateRange.from, timeTo, timezone).getTime() + 60_000 - 1;
  // A same-day time window such as 22:00–06:00 crosses midnight.
  if (end < start) end += DAY_IN_MS;
  return [start, end];
};

type HistoryFilterOptions = {
  data: SensorData[];
  dateRange?: DateRange;
  timeFrom: string;
  timeTo: string;
  timezone: string;
  /** Active "last N hours" preset. When set it replaces the date/time
   * filtering entirely: a rolling window is instant-based and cannot be
   * expressed as calendar days plus a per-day time window. */
  lastHours?: number;
  now?: Date;
};

export const createDefaultHistoryDateRange = (): DateRange => ({
  from: new Date(Date.now() - DAY_IN_MS),
  to: new Date(),
});

export const parseTimeToMinutes = (value: string) => {
  const [hours, minutes] = value.split(":").map(Number);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return undefined;

  return hours * 60 + minutes;
};

export const isMinuteWithinRange = (
  currentMinutes: number,
  fromMinutes?: number,
  toMinutes?: number
): boolean => {
  if (fromMinutes === undefined && toMinutes === undefined) return true;

  if (fromMinutes !== undefined && toMinutes !== undefined) {
    if (fromMinutes <= toMinutes) {
      return currentMinutes >= fromMinutes && currentMinutes <= toMinutes;
    }

    return currentMinutes >= fromMinutes || currentMinutes <= toMinutes;
  }

  if (fromMinutes !== undefined) {
    return currentMinutes >= fromMinutes;
  }

  return currentMinutes <= toMinutes!;
};

const padNumber = (value: number) => String(value).padStart(2, "0");

const getLocalDateKey = (value: Date) =>
  `${value.getFullYear()}-${padNumber(value.getMonth() + 1)}-${padNumber(value.getDate())}`;

const createZonedDateTimeFormatter = (timezone: string) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    hourCycle: "h23",
  });

const getDateKeyAndMinuteOfDay = (value: Date, formatter: Intl.DateTimeFormat) => {
  const parts = Object.fromEntries(formatter.formatToParts(value).map((part) => [part.type, part.value]));
  const hour = Number(parts.hour ?? "0");
  const minute = Number(parts.minute ?? "0");

  return {
    dateKey: `${parts.year}-${parts.month}-${parts.day}`,
    minuteOfDay: hour * 60 + minute,
  };
};

export const filterHistoricalData = ({ data, dateRange, timeFrom, timeTo, timezone, lastHours, now }: HistoryFilterOptions) => {
  if (lastHours !== undefined) {
    const cutoff = (now ?? new Date()).getTime() - lastHours * 60 * 60 * 1000;
    return data.filter((row) => row.timestamp.getTime() >= cutoff);
  }

  const fromDateKey = dateRange?.from ? getLocalDateKey(dateRange.from) : undefined;
  const toDateKey = dateRange?.to ? getLocalDateKey(dateRange.to) : undefined;
  const fromMinutes = parseTimeToMinutes(timeFrom);
  const toMinutes = parseTimeToMinutes(timeTo);
  const formatter = createZonedDateTimeFormatter(timezone);

  return data.filter((row) => {
    const { dateKey, minuteOfDay } = getDateKeyAndMinuteOfDay(row.timestamp, formatter);
    if (fromDateKey && dateKey < fromDateKey) return false;
    if (toDateKey && dateKey > toDateKey) return false;

    return isMinuteWithinRange(minuteOfDay, fromMinutes, toMinutes);
  });
};
