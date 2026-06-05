import { useMemo, useRef } from "react";

import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, LineChart as LineChartIcon, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

import { formatDateTimeLabel, formatTimeLabel } from "@/lib/datetime";
import { useApp } from "@/contexts/AppContext";
import {
  CHART_PALETTE,
  collectNumericMetricKeys,
  formatMetricValue,
  metricIcon,
  metricLabel,
  metricUnit,
} from "@/lib/metricCatalog";
import type { SensorData } from "@/data/types";
import { exportChartAsImage } from "./historicalChartExport";

const metricColor = (index: number) => CHART_PALETTE[index % CHART_PALETTE.length];

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

type ChartCardProps = {
  metric: string;
  Icon: LucideIcon;
  data: SensorData[];
  timezone: string;
  isDarkMode: boolean;
  colorIndex: number;
};

// One read-only plot for a single metric. The chart configurability (titles,
// metric selection, icons, colours, reordering) was removed and will be
// re-implemented later; for now each numeric metric simply gets its own plot.
const ChartCard: React.FC<ChartCardProps> = ({ metric, Icon, data, timezone, isDarkMode, colorIndex }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const iconRef = useRef<SVGSVGElement>(null);
  const color = metricColor(colorIndex);
  const unit = metricUnit(metric);

  const chartData = useMemo(
    () =>
      data.map(({ timestamp, ...metrics }) => ({
        ...metrics,
        time: formatTimeLabel(timestamp, timezone),
        fullTime: formatDateTimeLabel(timestamp, timezone),
      })),
    [data, timezone]
  );

  const formatYAxisTick = (value: number | string) => (unit ? `${value} ${unit}` : `${value}`);

  return (
    <div className="widget-shell-stroke rounded-2xl border border-border bg-card/70 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon ref={iconRef} className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-2xl font-bold text-foreground">{metricLabel(metric)}</h2>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Export chart image"
          onClick={() => {
            if (chartRef.current) {
              void exportChartAsImage(chartRef.current, {
                title: metricLabel(metric),
                icon: iconRef.current,
              });
            }
          }}
          className="btn-icon-panel h-8 w-8"
        >
          <Download className="h-4 w-4" />
        </Button>
      </div>

      <div ref={chartRef} className="h-[280px] w-full rounded-lg bg-background p-2">
        {chartData.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-lg text-sm text-muted-foreground">
            No data available for the selected range.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDarkMode ? "hsl(var(--sidebar-border))" : "hsl(var(--muted-foreground))"}
                strokeOpacity={isDarkMode ? 0.35 : 0.45}
              />
              <XAxis
                dataKey="time"
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
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
                isAnimationActive
                animationDuration={400}
                animationEasing="ease-out"
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
}

export const HistoricalCharts: React.FC<HistoricalChartsProps> = ({ data }) => {
  const { timezone, isDarkMode } = useApp();
  // One plot per numeric metric present in the (already date-filtered) data.
  const metrics = useMemo(() => collectNumericMetricKeys(data), [data]);

  if (metrics.length === 0) {
    return (
      <div className="flex min-h-[340px] flex-col items-center justify-center gap-4 rounded-2xl bg-background p-6 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border/70 bg-card">
          <LineChartIcon className="h-7 w-7 text-muted-foreground" />
        </div>
        <div className="space-y-1">
          <p className="text-base font-semibold text-foreground">No data available</p>
          <p className="text-sm text-muted-foreground">
            There is no sensor data for the selected range.
          </p>
        </div>
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
            data={data}
            timezone={timezone}
            isDarkMode={isDarkMode}
            colorIndex={index}
          />
        );
      })}
    </div>
  );
};
