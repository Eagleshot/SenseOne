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

/** True when the two instants fall on different calendar days in the zone —
 * the signal that chart axis ticks need a date, not just a time. */
export const spansMultipleDays = (first: Date, last: Date, timeZone?: string) => {
  const tz = resolveTimeZone(timeZone);
  return formatDateKey(first, tz) !== formatDateKey(last, tz);
};

const formatShortDateIntl = (timestamp: Date, timeZone: string) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "short",
    day: "numeric",
  }).format(timestamp);

/** Chart axis tick: "14:00" within a single day, "Jun 9, 14:00" across days
 * (time-only labels repeat ambiguously on multi-day ranges). */
export const formatChartTickLabel = (timestamp: Date, timeZone: string | undefined, includeDate: boolean) => {
  const tz = resolveTimeZone(timeZone);
  const time = formatTimeLabelIntl(timestamp, tz);
  return includeDate ? `${formatShortDateIntl(timestamp, tz)}, ${time}` : time;
};

// "in about 5 minutes" -> "in 5 min.": drop date-fns' "about " hedge and
// abbreviate "minutes". Shared by the status / weather "last online" labels.
export const formatRelativeShort = (date: Date) =>
  formatDistanceToNow(date, { addSuffix: true }).replace("about ", "").replace(/minutes?/g, "min.");

// "Next Online" countdown to a future instant: under a minute -> "in less than
// a min.", under an hour -> "in N min.", otherwise "in H h" (minutes dropped on
// the hour) or "in H h M min.". `now` is passed in so the result is deterministic.
export const formatCountdown = (target: Date, now: Date): string => {
  const totalMinutes = Math.round((target.getTime() - now.getTime()) / 60000);
  if (totalMinutes < 1) return "in less than a min.";
  if (totalMinutes < 60) return `in ${totalMinutes} min.`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes === 0 ? `in ${hours} h` : `in ${hours} h ${minutes} min.`;
};

// ---- Schedule time-of-day conversion ----------------------------------------
// The station schedule (start/stop) is stored and sent to the device in UTC;
// the settings UI edits it in the viewer's effective display timezone. Both
// helpers anchor on TODAY's date (a bare "HH:MM" has no date, and the zone
// offset depends on one), so across a DST change the stored UTC window keeps
// its instant and the displayed wall-clock time shifts by the offset change.

const formatHHMM = (instant: Date, timeZone: string) =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23", // never "24:00", which a time input rejects
  }).format(instant);

const parseHHMM = (time: string): [number, number] => {
  const [hours, minutes] = time.split(":").map(Number);
  return [hours, minutes];
};

/** The instant's wall clock in `timeZone`, re-encoded as if it were UTC —
 * the standard Intl trick to recover a zone's UTC offset without a tz library:
 * offset(instant) = wallClockAsUtcMs(instant) - instant. */
const wallClockAsUtcMs = (instant: Date, timeZone: string): number => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const get = (type: string) => Number(parts.find((part) => part.type === type)?.value);
  return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
};

/** Convert a calendar date plus wall-clock time in `timeZone` to its real
 * instant. Calendar picker dates intentionally use their machine-local
 * year/month/day fields; those fields represent the day the user clicked. */
export const zonedDateTimeToInstant = (date: Date, time: string, timeZone: string): Date => {
  const [hours, minutes] = parseHHMM(time);
  const desiredWallMs = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes);
  const offsetAt = (ms: number) => wallClockAsUtcMs(new Date(ms), timeZone) - ms;
  let instant = desiredWallMs - offsetAt(desiredWallMs);
  instant = desiredWallMs - offsetAt(instant);
  return new Date(instant);
};

/** "HH:MM" UTC -> "HH:MM" wall clock in `timeZone`, on today's date. */
export const utcTimeOfDayToZoned = (time: string, timeZone: string, now: Date = new Date()): string => {
  const [hours, minutes] = parseHHMM(time);
  const instant = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hours, minutes));
  return formatHHMM(instant, timeZone);
};

/** "HH:MM" wall clock in `timeZone` -> "HH:MM" UTC, on today's date in that
 * zone. During a DST transition a nonexistent/ambiguous wall time resolves to
 * a nearby instant — good enough for a capture schedule. */
export const zonedTimeOfDayToUtc = (time: string, timeZone: string, now: Date = new Date()): string => {
  const [hours, minutes] = parseHHMM(time);
  const todayWallMs = wallClockAsUtcMs(now, timeZone);
  const dayStartMs = todayWallMs - (todayWallMs % 86400000);
  const desiredWallMs = dayStartMs + (hours * 60 + minutes) * 60000;
  const offsetAt = (ms: number) => wallClockAsUtcMs(new Date(ms), timeZone) - ms;
  // Two passes: the first guesses using the offset at the desired wall time
  // read as UTC; the second re-reads the offset at that candidate instant so
  // times near a DST switch settle on the correct side.
  let instant = desiredWallMs - offsetAt(desiredWallMs);
  instant = desiredWallMs - offsetAt(instant);
  return formatHHMM(new Date(instant), "UTC");
};

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
