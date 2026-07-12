import type { DateRange } from "react-day-picker";

import { SensorData } from "@/data/types";

const DAY_IN_MS = 24 * 60 * 60 * 1000;

// How much history is fetched from the backend. The default matches the
// fetch on page load; the maximum mirrors the backend's cap (hours<=168).
export const DEFAULT_HISTORY_HOURS = 24;
export const MAX_HISTORY_HOURS = 168;

/** Backend fetch window (in hours back from now) needed to cover a picked
 * range: from the start of the range's first day, clamped to the backend cap
 * and never below the default (so the latest-reading consumers always have
 * the most recent day). */
export const historyWindowHoursForRange = (from: Date | undefined, now: Date = new Date()): number => {
  if (!from) return DEFAULT_HISTORY_HOURS;
  const startOfFromDay = new Date(from);
  startOfFromDay.setHours(0, 0, 0, 0);
  const hours = Math.ceil((now.getTime() - startOfFromDay.getTime()) / (60 * 60 * 1000));
  return Math.min(MAX_HISTORY_HOURS, Math.max(DEFAULT_HISTORY_HOURS, hours));
};

/** Earliest calendar day the date picker should allow: the start of the day
 * that the backend's maximum lookback window can still reach. */
export const minSelectableHistoryDate = (now: Date = new Date()): Date => {
  const earliest = new Date(now.getTime() - MAX_HISTORY_HOURS * 60 * 60 * 1000);
  earliest.setHours(0, 0, 0, 0);
  return earliest;
};

type HistoryFilterOptions = {
  data: SensorData[];
  dateRange?: DateRange;
  timeFrom: string;
  timeTo: string;
  timezone: string;
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

export const filterHistoricalData = ({ data, dateRange, timeFrom, timeTo, timezone }: HistoryFilterOptions) => {
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

