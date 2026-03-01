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

export const formatDateTimeLabel = (timestamp: Date, timeZone?: string) => {
  const tz = resolveTimeZone(timeZone);
  const dateKey = formatDateKey(timestamp, tz);
  const todayKey = formatDateKey(new Date(), tz);
  const yesterdayKey = formatDateKey(new Date(Date.now() - 24 * 60 * 60 * 1000), tz);

  const dateLabel =
    dateKey === todayKey ? "Today" : dateKey === yesterdayKey ? "Yesterday" : formatDateLabel(timestamp, tz);

  const timeLabel = formatTimeLabelIntl(timestamp, tz);
  return `${dateLabel} | ${timeLabel}`;
};

export const formatTimeLabel = (timestamp: Date, timeZone?: string) => {
  const tz = resolveTimeZone(timeZone);
  return formatTimeLabelIntl(timestamp, tz);
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
