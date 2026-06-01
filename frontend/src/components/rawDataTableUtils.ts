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

const numericSortValue = (value: SensorMetricValue | Date | undefined, direction: SortDirection) =>
  typeof value === "number" ? value : direction === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;

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
    const aVal = sortField === "timestamp" ? a.timestamp.getTime() : numericSortValue(a[sortField], sortDirection);
    const bVal = sortField === "timestamp" ? b.timestamp.getTime() : numericSortValue(b[sortField], sortDirection);
    return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
  });

  return working;
};

export const paginateRows = <T,>(data: T[], page: number, itemsPerPage: number) =>
  data.slice((page - 1) * itemsPerPage, page * itemsPerPage);

const csvHeader = (column: string): string => {
  const unit = metricUnit(column);
  return unit ? `${metricLabel(column)} (${unit})` : metricLabel(column);
};

export const buildSensorCsv = (data: SensorData[], timezone: string, columns: string[]) => {
  const headers = ["Timestamp", ...columns.map(csvHeader)];
  const rows = data.map((row) => [
    formatCsvTimestamp(row.timestamp, timezone),
    ...columns.map((column) => cellValue(row[column])),
  ]);

  return [headers, ...rows].map((row) => row.join(",")).join("\n");
};

export const sensorCsvFilename = (date = new Date()) => `sensor-data-${format(date, "yyyy-MM-dd")}.csv`;
