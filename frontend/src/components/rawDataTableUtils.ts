import { format } from "date-fns";

import type { SensorData } from "@/data/types";
import { formatCsvTimestamp, formatDateTimeLabel } from "@/lib/datetime";
import { TEMPERATURE_UNIT } from "@/lib/units";

export type SortField = "timestamp" | "temperature" | "humidity" | "battery" | "windSpeed" | "pressure";
export type SortDirection = "asc" | "desc";

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
}: {
  data: SensorData[];
  formattedTimestamps: Map<SensorData, string>;
  searchQuery: string;
  sortField: SortField;
  sortDirection: SortDirection;
}) => {
  let working = [...data];

  if (searchQuery.trim()) {
    const query = searchQuery.toLowerCase();
    working = working.filter((row) => {
      const dateStr = (formattedTimestamps.get(row) ?? "").toLowerCase();
      const values = [row.temperature, row.humidity, row.battery, row.windSpeed, row.pressure]
        .map(String)
        .join(" ");
      return dateStr.includes(query) || values.includes(query);
    });
  }

  working.sort((a, b) => {
    const aVal = sortField === "timestamp" ? a.timestamp.getTime() : a[sortField];
    const bVal = sortField === "timestamp" ? b.timestamp.getTime() : b[sortField];
    return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
  });

  return working;
};

export const paginateRows = <T,>(data: T[], page: number, itemsPerPage: number) =>
  data.slice((page - 1) * itemsPerPage, page * itemsPerPage);

export const buildSensorCsv = (data: SensorData[], timezone: string) => {
  const headers = [
    "Timestamp",
    `Temperature (${TEMPERATURE_UNIT})`,
    "Humidity (%)",
    "Battery (%)",
    "Wind (km/h)",
    "Pressure (hPa)",
  ];
  const rows = data.map((row) => [
    formatCsvTimestamp(row.timestamp, timezone),
    row.temperature,
    row.humidity,
    row.battery,
    row.windSpeed,
    row.pressure,
  ]);

  return [headers, ...rows].map((row) => row.join(",")).join("\n");
};

export const sensorCsvFilename = (date = new Date()) => `sensor-data-${format(date, "yyyy-MM-dd")}.csv`;
