import { endOfDay, startOfDay } from "date-fns";
import type { DateRange } from "react-day-picker";

import { SensorData } from "@/data/types";

const DAY_IN_MS = 24 * 60 * 60 * 1000;

type HistoryFilterOptions = {
  data: SensorData[];
  dateRange?: DateRange;
  timeFrom: string;
  timeTo: string;
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

export const filterHistoricalData = ({ data, dateRange, timeFrom, timeTo }: HistoryFilterOptions) => {
  const fromDate = dateRange?.from ? startOfDay(dateRange.from) : undefined;
  const toDate = dateRange?.to ? endOfDay(dateRange.to) : undefined;
  const fromMinutes = parseTimeToMinutes(timeFrom);
  const toMinutes = parseTimeToMinutes(timeTo);

  return data.filter((row) => {
    const timestamp = row.timestamp;
    if (fromDate && timestamp < fromDate) return false;
    if (toDate && timestamp > toDate) return false;

    const currentMinutes = timestamp.getHours() * 60 + timestamp.getMinutes();
    return isMinuteWithinRange(currentMinutes, fromMinutes, toMinutes);
  });
};
