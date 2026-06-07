import { format } from "date-fns";

import type { SensorData, SensorMetricValue } from "@/data/types";
import { formatCsvTimestamp, formatDateTimeLabel } from "@/lib/datetime";
import { collectMetricKeys, metricLabel, metricUnit } from "@/lib/metricCatalog";

// "timestamp" or any metric key present in the data.
export type SortField = string;
export type SortDirection = "asc" | "desc";

export { collectMetricKeys };

const cellValue = (value: SensorMetricValue | Date | undefined): string =>
  value === null || value === undefined || value instanceof Date ? "" : `${value}`;

const isMissingValue = (value: SensorMetricValue | Date | undefined): boolean =>
  value === null || value === undefined || value === "";

// Compare two cell values for sorting: numbers numerically, everything else
// lexically (numeric-aware so "1.10" > "1.9"). Missing values always sort to the
// end regardless of direction. Using a real comparator (not Infinity arithmetic)
// is what lets string columns like wakeReason actually sort.
const compareCellValues = (
  a: SensorMetricValue | Date | undefined,
  b: SensorMetricValue | Date | undefined,
  direction: SortDirection,
): number => {
  if (isMissingValue(a) || isMissingValue(b)) {
    if (isMissingValue(a) && isMissingValue(b)) return 0;
    return isMissingValue(a) ? 1 : -1;
  }
  const result =
    typeof a === "number" && typeof b === "number"
      ? a - b
      : String(a).localeCompare(String(b), undefined, { numeric: true });
  return direction === "asc" ? result : -result;
};

export const createFormattedTimestampMap = (data: SensorData[], timezone: string) =>
  new Map(data.map((row) => [row, formatDateTimeLabel(row.timestamp, timezone)]));

export const createSensorRowKeyMap = (data: SensorData[]) =>
  new Map(data.map((row, index) => [row, `${row.timestamp.toISOString()}-${index}`]));

export const filterAndSortSensorRows = ({
  data,
  formattedTimestamps,
  searchQuery,
  sortField,
  sortDirection,
  columns,
}: {
  data: SensorData[];
  formattedTimestamps: Map<SensorData, string>;
  searchQuery: string;
  sortField: SortField;
  sortDirection: SortDirection;
  columns: string[];
}) => {
  let working = [...data];

  if (searchQuery.trim()) {
    const query = searchQuery.toLowerCase();
    working = working.filter((row) => {
      const dateStr = (formattedTimestamps.get(row) ?? "").toLowerCase();
      const values = columns.map((column) => cellValue(row[column])).join(" ").toLowerCase();
      return dateStr.includes(query) || values.includes(query);
    });
  }

  working.sort((a, b) => {
    if (sortField === "timestamp") {
      const diff = a.timestamp.getTime() - b.timestamp.getTime();
      return sortDirection === "asc" ? diff : -diff;
    }
    return compareCellValues(a[sortField], b[sortField], sortDirection);
  });

  return working;
};

export const paginateRows = <T,>(data: T[], page: number, itemsPerPage: number) =>
  data.slice((page - 1) * itemsPerPage, page * itemsPerPage);

const csvHeader = (column: string): string => {
  const unit = metricUnit(column);
  return unit ? `${metricLabel(column)} (${unit})` : metricLabel(column);
};

// RFC 4180: a field containing a comma, quote, or newline must be wrapped in
// double quotes with internal quotes doubled. Without this a value like
// "Motion, low battery" would split into two columns and corrupt the row.
const escapeCsvCell = (value: string): string =>
  /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;

export const buildSensorCsv = (data: SensorData[], timezone: string, columns: string[]) => {
  const headers = ["Timestamp", ...columns.map(csvHeader)];
  const rows = data.map((row) => [
    formatCsvTimestamp(row.timestamp, timezone),
    ...columns.map((column) => cellValue(row[column])),
  ]);

  return [headers, ...rows].map((row) => row.map(escapeCsvCell).join(",")).join("\n");
};

export const sensorCsvFilename = (date = new Date()) => `sensor-data-${format(date, "yyyy-MM-dd")}.csv`;
