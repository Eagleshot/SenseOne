import { formatDistanceToNow } from "date-fns";

const resolveTimeZone = (timeZone?: string) =>
  timeZone || Intl.DateTimeFormat().resolvedOptions().timeZone;

const formatDateKey = (timestamp: Date, timeZone: string) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(timestamp);

const formatDateLabel = (timestamp: Date, timeZone: string) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(timestamp);

const formatTimeLabelIntl = (timestamp: Date, timeZone: string) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(timestamp);

const dayBefore = (dateKey: string): string => {
  const [year, month, day] = dateKey.split("-").map(Number);
  // Step back one calendar day in UTC (no DST), so the result is exact even when
  // the local zone changed offset overnight; Date normalises month/year rollover.
  return new Date(Date.UTC(year, month - 1, day - 1)).toISOString().slice(0, 10);
};

export const formatDateTimeLabel = (timestamp: Date, timeZone?: string) => {
  const tz = resolveTimeZone(timeZone);
  const dateKey = formatDateKey(timestamp, tz);
  const todayKey = formatDateKey(new Date(), tz);
  // Derive "yesterday" from today's key, not by subtracting 24h of ms, which
  // would skip or repeat a day across a DST transition.
  const yesterdayKey = dayBefore(todayKey);

  const dateLabel =
    dateKey === todayKey ? "Today" : dateKey === yesterdayKey ? "Yesterday" : formatDateLabel(timestamp, tz);

  const timeLabel = formatTimeLabelIntl(timestamp, tz);
  return `${dateLabel} | ${timeLabel}`;
};

export const formatTimeLabel = (timestamp: Date, timeZone?: string) => {
  const tz = resolveTimeZone(timeZone);
  return formatTimeLabelIntl(timestamp, tz);
};

// "in about 5 minutes" -> "in 5 min.": drop date-fns' "about " hedge and
// abbreviate "minutes". Shared by the status / weather "last online" labels.
export const formatRelativeShort = (date: Date) =>
  formatDistanceToNow(date, { addSuffix: true }).replace("about ", "").replace(/minutes?/g, "min.");

export const formatCsvTimestamp = (timestamp: Date, timeZone?: string) => {
  const tz = resolveTimeZone(timeZone);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(timestamp);
  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day} ${map.hour}:${map.minute}:${map.second}`;
};

