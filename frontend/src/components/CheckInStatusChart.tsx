import { useMemo, useRef } from "react";

import { Area, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";

import { formatDateTimeLabel, formatTimeLabel } from "@/lib/datetime";
import { useApp } from "@/contexts/AppContext";
import type { SensorData } from "@/data/types";
import { exportChartAsImage } from "./historicalChartExport";

// Matches the backend's NEXT_ONLINE_STATUS_BUFFER_MINUTES grace (constants.py),
// so this chart agrees with the station's online badge.
const GRACE_MS = 5 * 60 * 1000;
const ONLINE_COLOR = "hsl(142 71% 45%)";

type StatusPoint = { t: number; status: 0 | 1 };

// Each check-in counts as online over [recorded_at, next_online + grace]. Merge
// those windows, then flatten to step points: a stepAfter line holds each point's
// value until the next point, so {start,1}{end,0} draws online over [start,end]
// and offline over the gap until the next window.
const buildStatusPoints = (data: SensorData[]): StatusPoint[] => {
  const windows: Array<[number, number]> = [];
  for (const row of data) {
    const start = row.timestamp.getTime();
    const end = row.nextStart instanceof Date ? row.nextStart.getTime() + GRACE_MS : start;
    windows.push([start, Math.max(start, end)]);
  }
  if (windows.length === 0) return [];

  windows.sort((a, b) => a[0] - b[0]);
  const merged: Array<[number, number]> = [[...windows[0]]];
  for (let i = 1; i < windows.length; i += 1) {
    const last = merged[merged.length - 1];
    const [start, end] = windows[i];
    if (start <= last[1]) {
      last[1] = Math.max(last[1], end);
    } else {
      merged.push([start, end]);
    }
  }

  const points: StatusPoint[] = [];
  for (const [start, end] of merged) {
    points.push({ t: start, status: 1 });
    points.push({ t: end, status: 0 });
  }
  return points;
};

const StatusTooltip = ({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ value: number; payload: { fullTime: string } }>;
}) => {
  if (!active || !payload || payload.length === 0) return null;
  const online = Number(payload[0]?.value) === 1;
  return (
    <div className="rounded-lg border border-border bg-[hsl(var(--sidebar-background))] p-3 shadow-soft-lg">
      <p className="text-xs text-muted-foreground">{payload[0]?.payload?.fullTime}</p>
      <p
        className="mt-1 text-xs font-semibold"
        style={{ color: online ? ONLINE_COLOR : "hsl(var(--muted-foreground))" }}
      >
        {online ? "Online" : "Offline"}
      </p>
    </div>
  );
};

interface CheckInStatusChartProps {
  data: SensorData[];
}

// Online/offline status over real time, derived from each check-in's next-online
// hint. Filled/green = online, baseline = offline.
export const CheckInStatusChart: React.FC<CheckInStatusChartProps> = ({ data }) => {
  const { timezone, isDarkMode } = useApp();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const iconRef = useRef<SVGSVGElement>(null);

  const points = useMemo(
    () =>
      buildStatusPoints(data).map((point) => ({
        ...point,
        fullTime: formatDateTimeLabel(new Date(point.t), timezone),
      })),
    [data, timezone]
  );

  return (
    <div className="widget-shell-stroke rounded-2xl border border-border bg-card/70 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Wifi ref={iconRef} className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-2xl font-bold text-foreground">Check-in status</h2>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Export chart image"
          onClick={() => {
            if (chartRef.current) {
              void exportChartAsImage(chartRef.current, { title: "Check-in status", icon: iconRef.current });
            }
          }}
          className="btn-icon-panel h-8 w-8"
        >
          <Download className="h-4 w-4" />
        </Button>
      </div>

      <div ref={chartRef} className="h-[160px] w-full rounded-lg bg-background p-2">
        {points.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-lg text-sm text-muted-foreground">
            No check-in data for the selected date range.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDarkMode ? "hsl(var(--sidebar-border))" : "hsl(var(--muted-foreground))"}
                strokeOpacity={isDarkMode ? 0.35 : 0.45}
              />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                minTickGap={48}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickFormatter={(value: number) => formatTimeLabel(new Date(value), timezone)}
              />
              <YAxis
                domain={[0, 1]}
                ticks={[0, 1]}
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                width={72}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickFormatter={(value: number) => (value === 1 ? "Online" : "Offline")}
              />
              <Tooltip content={<StatusTooltip />} />
              <Area
                type="stepAfter"
                dataKey="status"
                stroke={ONLINE_COLOR}
                strokeWidth={2}
                fill={ONLINE_COLOR}
                fillOpacity={0.25}
                isAnimationActive={false}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
