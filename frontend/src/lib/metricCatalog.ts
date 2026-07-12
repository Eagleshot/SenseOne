import {
  Activity,
  Battery,
  Cpu,
  Droplets,
  Gauge,
  Power,
  Signal,
  Tag,
  Thermometer,
  Zap,
  type LucideIcon,
} from "lucide-react";

import type { SensorData, SensorMetricValue } from "@/data/types";
import { TEMPERATURE_UNIT } from "@/lib/units";

// "status"  -> also surfaces as a quick-info card (battery, reception)
// "measurement" / "event" -> appears in the data table (and charts if numeric)
// "info"    -> device housekeeping shown elsewhere (e.g. firmware in the
//              settings header); excluded from the data table.
export type MetricKind = "status" | "measurement" | "event" | "info";

export interface MetricDef {
  label: string;
  unit?: string;
  icon: LucideIcon;
  kind: MetricKind;
}

// Known metrics with friendly labels, units and icons. This is the single
// source of display metadata; any metric a device sends that is NOT listed
// here still renders, using a humanized key and no unit.
// Declaration order doubles as the preferred display order for tables/charts:
// measurements first, then device housekeeping. Status cards (battery,
// reception) use STATUS_METRIC_KEYS, which preserves this order.
export const METRIC_CATALOG: Record<string, MetricDef> = {
  temperature: { label: "Temperature", unit: TEMPERATURE_UNIT, icon: Thermometer, kind: "measurement" },
  humidity: { label: "Humidity", unit: "%", icon: Droplets, kind: "measurement" },
  pressure: { label: "Pressure", unit: "hPa", icon: Gauge, kind: "measurement" },
  battery: { label: "Battery", unit: "%", icon: Battery, kind: "status" },
  reception: { label: "Reception", unit: "%", icon: Signal, kind: "status" },
  voltage: { label: "Voltage", unit: "V", icon: Zap, kind: "measurement" },
  deviceTemperature: { label: "Device Temp", unit: TEMPERATURE_UNIT, icon: Cpu, kind: "measurement" },
  wakeReason: { label: "Wake Reason", icon: Power, kind: "event" },
  firmwareVersion: { label: "Firmware", icon: Tag, kind: "info" },
};

// Preferred display order for known metrics. Unknown metrics sort after these,
// alphabetically.
const CATALOG_ORDER = Object.keys(METRIC_CATALOG);

// "Status" metrics shown as quick-info cards, in a stable order.
export const STATUS_METRIC_KEYS = CATALOG_ORDER.filter(
  (key) => METRIC_CATALOG[key].kind === "status"
);

// Status metrics (battery, reception) are 0-100% where higher is better.
export type StatusLevel = "success" | "warning" | "error";

export const statusLevelForValue = (value: number): StatusLevel =>
  value >= 60 ? "success" : value >= 30 ? "warning" : "error";

// Line colours for charts, cycled by series index.
export const CHART_PALETTE = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
];

export const humanizeMetricKey = (key: string): string =>
  key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());

export const metricDef = (key: string): MetricDef | undefined => METRIC_CATALOG[key];

export const metricLabel = (key: string): string => METRIC_CATALOG[key]?.label ?? humanizeMetricKey(key);

export const metricUnit = (key: string): string => METRIC_CATALOG[key]?.unit ?? "";

export const metricIcon = (key: string): LucideIcon => METRIC_CATALOG[key]?.icon ?? Activity;

export const formatMetricValue = (key: string, value: SensorMetricValue | Date | undefined): string => {
  if (typeof value === "string") return value || "—";
  if (typeof value !== "number") return "—";
  const unit = metricUnit(key);
  if (!unit) return `${value}`;
  return unit === "%" ? `${value}%` : `${value} ${unit}`;
};

export const orderMetricKeys = (keys: Iterable<string>): string[] => {
  const unique = Array.from(new Set(keys));
  return unique.sort((a, b) => {
    const indexA = CATALOG_ORDER.indexOf(a);
    const indexB = CATALOG_ORDER.indexOf(b);
    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
    if (indexA !== -1) return -1;
    if (indexB !== -1) return 1;
    return a.localeCompare(b);
  });
};

const metricEntries = (row: SensorData): [string, SensorMetricValue | Date | undefined][] =>
  // "timestamp" and "nextStart" are dedicated, timestamp-formatted columns, not metrics.
  Object.entries(row).filter(([key]) => key !== "timestamp" && key !== "nextStart");

const collectKeys = (
  data: SensorData[],
  include: (key: string, value: SensorMetricValue | Date | undefined) => boolean,
): string[] => {
  const keys = new Set<string>();
  for (const row of data) {
    for (const [key, value] of metricEntries(row)) {
      if (include(key, value)) keys.add(key);
    }
  }
  return orderMetricKeys(keys);
};

/**
 * Metric keys to show as data-table columns, ordered for display.
 * Excludes "info" metrics (device housekeeping surfaced elsewhere, e.g.
 * firmware version in the settings header).
 */
export const collectMetricKeys = (data: SensorData[]): string[] =>
  collectKeys(data, (key, value) => value !== undefined && metricDef(key)?.kind !== "info");

/** Metric keys with at least one numeric value — i.e. the chartable metrics. */
export const collectNumericMetricKeys = (data: SensorData[]): string[] =>
  collectKeys(data, (_key, value) => typeof value === "number");
