import { useMemo } from "react";

import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LineChart as LineChartIcon, type LucideIcon } from "lucide-react";

import { formatChartTickLabel, formatDateTimeLabel, spansMultipleDays } from "@/lib/datetime";
import { usePreferences } from "@/contexts/AppContext";
import {
  CHART_PALETTE,
  collectNumericMetricKeys,
  formatMetricValue,
  metricIcon,
  metricLabel,
  metricUnit,
} from "@/lib/metricCatalog";
import type { SensorData } from "@/data/types";
import type { HistoryTimeRange } from "@/lib/historyFilters";
import { CheckInStatusChart } from "./CheckInStatusChart";

const metricColor = (index: number) => CHART_PALETTE[index % CHART_PALETTE.length];
const X_TICK_COUNT = 6;

const timeRangeTicks = ([start, end]: HistoryTimeRange) =>
  Array.from({ length: X_TICK_COUNT }, (_, index) => start + ((end - start) * index) / (X_TICK_COUNT - 1));

const ChartTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number | null; color: string; payload: { fullTime: string } }>;
}) => {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-border bg-[hsl(var(--sidebar-background))] p-3 shadow-soft-lg">
      <p className="text-xs text-muted-foreground">{payload[0]?.payload?.fullTime}</p>
      <div className="mt-2 space-y-1">
        {payload.map((item) => {
          const metric = item.dataKey;
          return (
            <div key={metric} className="flex items-center justify-between gap-4 text-xs">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                {metricLabel(metric)}
              </span>
              <span className="font-semibold text-foreground">{formatMetricValue(metric, item.value)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

type ChartRow = Omit<SensorData, "timestamp"> & { time: number; fullTime: string };

type ChartCardProps = {
  metric: string;
  Icon: LucideIcon;
  chartData: ChartRow[];
  timeRange: HistoryTimeRange;
  timezone: string;
  isDarkMode: boolean;
  colorIndex: number;
};

// One read-only plot for a single metric. The chart configurability (titles,
// metric selection, icons, colours, reordering) was removed and will be
// re-implemented later; for now each numeric metric simply gets its own plot.
const ChartCard: React.FC<ChartCardProps> = ({
  metric,
  Icon,
  chartData,
  timeRange,
  timezone,
  isDarkMode,
  colorIndex,
}) => {
  const color = metricColor(colorIndex);
  const unit = metricUnit(metric);
  const xTicks = timeRangeTicks(timeRange);
  const includeDate = spansMultipleDays(new Date(timeRange[0]), new Date(timeRange[1]), timezone);

  const formatYAxisTick = (value: number | string) => (unit ? `${value} ${unit}` : `${value}`);

  return (
    <div className="widget-shell-stroke rounded-2xl border border-border bg-card/70 p-4">
      <div className="mb-4 flex items-center gap-2">
        <Icon className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-lg font-semibold text-foreground">{metricLabel(metric)}</h3>
      </div>

      <div className="h-[280px] w-full rounded-lg bg-background p-2">
        {chartData.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-lg text-sm text-muted-foreground">
            No data available for the selected date range.
          </div>
        ) : (
          // debounce: re-render once after a resize settles, not per animation
          // frame (the sidebar open/close animates the main column's width).
          <ResponsiveContainer width="100%" height="100%" debounce={200}>
            <ComposedChart data={chartData} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDarkMode ? "hsl(var(--sidebar-border))" : "hsl(var(--muted-foreground))"}
                strokeOpacity={isDarkMode ? 0.35 : 0.45}
              />
              <XAxis
                dataKey="time"
                type="number"
                scale="time"
                domain={[timeRange[0], timeRange[1]]}
                ticks={xTicks}
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                minTickGap={48}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickFormatter={(value: number) => formatChartTickLabel(new Date(value), timezone, includeDate)}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickFormatter={formatYAxisTick}
                width={72}
              />
              <Tooltip content={<ChartTooltip />} />
              <Line
                type="monotone"
                dataKey={metric}
                stroke={color}
                strokeWidth={2.2}
                dot={false}
                activeDot={{ r: 4, fill: color }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

interface HistoricalChartsProps {
  data: SensorData[];
  timeRange: HistoryTimeRange;
  /** True when the sensor-history request failed (as opposed to "no readings"). */
  loadFailed?: boolean;
}

export const HistoricalCharts: React.FC<HistoricalChartsProps> = ({ data, timeRange, loadFailed = false }) => {
  const { timezone, isDarkMode } = usePreferences();
  // One plot per numeric metric present in the (already date-filtered) data.
  const metrics = useMemo(() => collectNumericMetricKeys(data), [data]);
  // Map the rows (with their formatted time labels) once and share across cards,
  // rather than re-mapping the whole dataset inside every per-metric ChartCard.
  // Ranges crossing a day boundary get dated ticks — time-only labels would
  // repeat ambiguously ("14:00" three days in a row).
  const chartData = useMemo<ChartRow[]>(() => {
    if (data.length === 0) return [];
    return data.map(({ timestamp, ...values }) => ({
      ...values,
      time: timestamp.getTime(),
      fullTime: formatDateTimeLabel(timestamp, timezone),
    }));
  }, [data, timezone]);
  // The check-in status chart shows whenever any check-in carried a next-online hint.
  const hasStatus = useMemo(() => data.some((row) => row.nextStart instanceof Date), [data]);

  if (metrics.length === 0 && !hasStatus) {
    return (
      <div className="flex min-h-[340px] flex-col items-center justify-center gap-4 rounded-2xl bg-background p-6 text-center">
        <LineChartIcon className="h-7 w-7 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {loadFailed
            ? "Could not load sensor data for this station. Try again later."
            : "No data available for the selected date range."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {metrics.map((metric, index) => {
        const Icon = metricIcon(metric);
        return (
          <ChartCard
            key={metric}
            metric={metric}
            Icon={Icon}
            chartData={chartData}
            timeRange={timeRange}
            timezone={timezone}
            isDarkMode={isDarkMode}
            colorIndex={index}
          />
        );
      })}
      {hasStatus && <CheckInStatusChart data={data} timeRange={timeRange} />}
    </div>
  );
};
