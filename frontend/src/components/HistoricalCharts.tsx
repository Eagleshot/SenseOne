import React, { useEffect, useMemo, useRef, useState } from "react";

import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  Battery,
  Download,
  Droplets,
  Eye,
  Gauge,
  LineChart as LineChartIcon,
  Plus,
  Settings2,
  Thermometer,
  Trash2,
  Wind,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { formatDateTimeLabel, formatTimeLabel } from "@/lib/datetime";
import { useApp } from "@/contexts/AppContext";
import { cn } from "@/lib/utils";
import type { SensorData } from "@/data/types";

type MetricType =
  | "temperature"
  | "battery"
  | "humidity"
  | "windSpeed"
  | "pressure"
  | "visibility"
  | "uvIndex"
  | "dewPoint"
  | "feelsLike";

type ChartIconKey = "line" | "thermometer" | "battery" | "humidity" | "wind" | "gauge" | "activity" | "eye";

type ChartConfig = {
  id: string;
  title: string;
  icon: ChartIconKey;
  color: string;
  metrics: MetricType[];
};

type ChartDraft = Omit<ChartConfig, "id">;

const metricConfig: Record<MetricType, { label: string; unit: string; color: string }> = {
  temperature: { label: "Temperature", unit: "C", color: "hsl(var(--chart-1))" },
  battery: { label: "Battery Level", unit: "%", color: "hsl(var(--chart-2))" },
  humidity: { label: "Humidity", unit: "%", color: "hsl(var(--chart-3))" },
  windSpeed: { label: "Wind Speed", unit: "km/h", color: "hsl(var(--chart-1))" },
  pressure: { label: "Pressure", unit: "hPa", color: "hsl(var(--chart-2))" },
  visibility: { label: "Visibility", unit: "km", color: "hsl(var(--chart-3))" },
  uvIndex: { label: "UV Index", unit: "", color: "hsl(var(--chart-1))" },
  dewPoint: { label: "Dew Point", unit: "C", color: "hsl(var(--chart-2))" },
  feelsLike: { label: "Feels Like", unit: "C", color: "hsl(var(--chart-3))" },
};

const chartIconConfig: Record<ChartIconKey, React.ComponentType<{ className?: string }>> = {
  line: LineChartIcon,
  thermometer: Thermometer,
  battery: Battery,
  humidity: Droplets,
  wind: Wind,
  gauge: Gauge,
  activity: Activity,
  eye: Eye,
};

const chartIconOptions: Array<{ value: ChartIconKey; label: string }> = [
  { value: "line", label: "Line Chart" },
  { value: "thermometer", label: "Thermometer" },
  { value: "battery", label: "Battery" },
  { value: "humidity", label: "Droplets" },
  { value: "wind", label: "Wind" },
  { value: "gauge", label: "Gauge" },
  { value: "activity", label: "Activity" },
  { value: "eye", label: "Eye" },
];

const metricOptions = Object.keys(metricConfig) as MetricType[];
const chartThemeColorOptions = [
  { value: "hsl(var(--chart-1))", label: "Theme Chart 1" },
  { value: "hsl(var(--chart-2))", label: "Theme Chart 2" },
  { value: "hsl(var(--chart-3))", label: "Theme Chart 3" },
] as const;
type ChartThemeColorValue = (typeof chartThemeColorOptions)[number]["value"];
type ChartColorSelection = ChartThemeColorValue | "custom";

const createChartId = () => `chart-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const createDefaultChart = (label = "Temperature"): ChartConfig => ({
  id: createChartId(),
  title: label,
  icon: "thermometer",
  color: metricConfig.temperature.color,
  metrics: ["temperature"],
});

const sanitizeFileName = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "chart";

const DEFAULT_CUSTOM_COLOR = "#f97316";
const isValidHexColor = (value: string) => /^#[0-9a-fA-F]{6}$/.test(value);
const normalizeColorValue = (value: string) => value.trim().toLowerCase().replace(/\s+/g, "");
const getThemeColorValue = (value: string): ChartThemeColorValue | null => {
  const normalizedValue = normalizeColorValue(value);
  const match = chartThemeColorOptions.find((option) => normalizeColorValue(option.value) === normalizedValue);
  return match ? match.value : null;
};
const getColorSelection = (value: string): ChartColorSelection => {
  const themeColorValue = getThemeColorValue(value);
  if (themeColorValue) return themeColorValue;
  if (isValidHexColor(value)) return "custom";
  return chartThemeColorOptions[0].value;
};

const exportChartAsImage = async (container: HTMLDivElement, title: string) => {
  const svg = container.querySelector("svg");
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  const serializer = new XMLSerializer();
  const svgMarkup = serializer.serializeToString(svg);
  const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    await new Promise<void>((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const scale = 2;
        const canvas = document.createElement("canvas");
        canvas.width = Math.ceil(rect.width * scale);
        canvas.height = Math.ceil(rect.height * scale);
        const context = canvas.getContext("2d");
        if (!context) {
          reject(new Error("Unable to export chart image."));
          return;
        }

        context.scale(scale, scale);
        const backgroundColor = getComputedStyle(container).backgroundColor || "#ffffff";
        context.fillStyle = backgroundColor;
        context.fillRect(0, 0, rect.width, rect.height);
        context.drawImage(image, 0, 0, rect.width, rect.height);

        const link = document.createElement("a");
        link.href = canvas.toDataURL("image/png");
        link.download = `${sanitizeFileName(title)}.png`;
        link.click();
        resolve();
      };
      image.onerror = () => reject(new Error("Unable to export chart image."));
      image.src = svgUrl;
    });
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
};

type ChartCardProps = {
  config: ChartConfig;
  data: SensorData[];
  timezone: string;
  isDarkMode: boolean;
  index: number;
  total: number;
  onUpdate: (id: string, updates: Partial<ChartConfig>) => void;
  onMove: (id: string, direction: "up" | "down") => void;
  onRemove: (id: string) => void;
};

const ChartCard: React.FC<ChartCardProps> = ({
  config,
  data,
  timezone,
  isDarkMode,
  index,
  total,
  onUpdate,
  onMove,
  onRemove,
}) => {
  const Icon = chartIconConfig[config.icon];
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<ChartDraft>({
    title: config.title,
    icon: config.icon,
    color: config.color,
    metrics: config.metrics,
  });
  const [colorSelection, setColorSelection] = useState<ChartColorSelection>(() => getColorSelection(config.color));
  const [customColor, setCustomColor] = useState<string>(
    isValidHexColor(config.color) ? config.color : DEFAULT_CUSTOM_COLOR
  );

  useEffect(() => {
    if (!isEditing) return;
    setDraft({
      title: config.title,
      icon: config.icon,
      color: config.color,
      metrics: config.metrics,
    });
    setColorSelection(getColorSelection(config.color));
    setCustomColor(isValidHexColor(config.color) ? config.color : DEFAULT_CUSTOM_COLOR);
  }, [config, isEditing]);

  const chartData = useMemo(
    () =>
      data.map((row) => ({
        time: formatTimeLabel(row.timestamp, timezone),
        fullTime: formatDateTimeLabel(row.timestamp, timezone),
        temperature: row.temperature,
        battery: row.battery,
        humidity: row.humidity,
        windSpeed: row.windSpeed,
        pressure: row.pressure,
        visibility: row.visibility,
        uvIndex: row.uvIndex,
        dewPoint: row.dewPoint,
        feelsLike: row.feelsLike,
      })),
    [data, timezone]
  );

  const toggleMetric = (metric: MetricType, checked: boolean) => {
    setDraft((prev) => {
      if (checked) {
        if (prev.metrics.includes(metric)) return prev;
        return { ...prev, metrics: [...prev.metrics, metric] };
      }
      if (prev.metrics.length === 1) return prev;
      return { ...prev, metrics: prev.metrics.filter((item) => item !== metric) };
    });
  };

  const handleSave = () => {
    const nextColor =
      colorSelection === "custom" ? (isValidHexColor(customColor) ? customColor : DEFAULT_CUSTOM_COLOR) : draft.color;
    onUpdate(config.id, {
      title: draft.title.trim() || "Custom Chart",
      icon: draft.icon,
      color: nextColor,
      metrics: draft.metrics.length ? draft.metrics : ["temperature"],
    });
    setIsEditing(false);
  };

  const handleColorSelectionChange = (value: ChartColorSelection) => {
    setColorSelection(value);
    if (value === "custom") {
      const nextCustomColor = isValidHexColor(customColor) ? customColor : DEFAULT_CUSTOM_COLOR;
      setDraft((prev) => ({ ...prev, color: nextCustomColor }));
      return;
    }
    setDraft((prev) => ({ ...prev, color: value }));
  };

  const formatMetricValue = (metric: MetricType, value: number) => {
    const unit = metricConfig[metric].unit;
    return unit ? `${value} ${unit}` : `${value}`;
  };

  const ChartTooltip = ({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: Array<{ dataKey: string; value: number; color: string; payload: { fullTime: string } }>;
  }) => {
    if (!active || !payload || payload.length === 0) return null;
    return (
      <div className="rounded-lg border border-border bg-[hsl(var(--sidebar-background))] p-3 shadow-soft-lg">
        <p className="text-xs text-muted-foreground">{payload[0]?.payload?.fullTime}</p>
        <div className="mt-2 space-y-1">
          {payload.map((item) => {
            const metric = item.dataKey as MetricType;
            if (!(metric in metricConfig)) return null;
            return (
              <div key={metric} className="flex items-center justify-between gap-4 text-xs">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                  {metricConfig[metric].label}
                </span>
                <span className="font-semibold text-foreground">{formatMetricValue(metric, item.value)}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="rounded-2xl border border-border bg-card/70 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center" style={{ color: config.color }}>
            <Icon className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-foreground">{config.title}</p>
            <p className="text-xs text-muted-foreground">
              {config.metrics.map((metric) => metricConfig[metric].label).join(" + ")}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Move chart up"
            disabled={index === 0}
            onClick={() => onMove(config.id, "up")}
            className="h-8 w-8"
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Move chart down"
            disabled={index === total - 1}
            onClick={() => onMove(config.id, "down")}
            className="h-8 w-8"
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
          <Dialog open={isEditing} onOpenChange={setIsEditing}>
            <DialogTrigger asChild>
              <Button type="button" variant="ghost" size="icon" aria-label="Edit chart" className="h-8 w-8">
                <Settings2 className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Edit Chart</DialogTitle>
                <DialogDescription>
                  Change title, icon, color theme/custom color, and metrics for this chart.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">Title</label>
                  <Input
                    value={draft.title}
                    onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
                    placeholder="Chart title"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">Icon</label>
                    <Select
                      value={draft.icon}
                      onValueChange={(value) => setDraft((prev) => ({ ...prev, icon: value as ChartIconKey }))}
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                      {chartIconOptions.map((option) => {
                        const OptionIcon = chartIconConfig[option.value];
                        return (
                          <SelectItem key={option.value} value={option.value}>
                            <span className="flex items-center gap-2">
                              <OptionIcon className="h-4 w-4" />
                              {option.label}
                            </span>
                          </SelectItem>
                        );
                      })}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">Color</label>
                    <div className="space-y-2">
                      <Select
                        value={colorSelection}
                        onValueChange={(value) => handleColorSelectionChange(value as ChartColorSelection)}
                      >
                        <SelectTrigger className="h-9">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {chartThemeColorOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              <span className="flex items-center gap-2">
                                <span
                                  className="h-3 w-3 rounded-full"
                                  style={{ backgroundColor: option.value }}
                                />
                                {option.label}
                              </span>
                            </SelectItem>
                          ))}
                          <SelectItem value="custom">
                            <span className="flex items-center gap-2">
                              <span
                                className="h-3 w-3 rounded-full border border-border"
                                style={{
                                  backgroundColor: isValidHexColor(customColor)
                                    ? customColor
                                    : DEFAULT_CUSTOM_COLOR,
                                }}
                              />
                              Custom Color
                            </span>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      {colorSelection === "custom" && (
                        <Input
                          type="color"
                          value={isValidHexColor(customColor) ? customColor : DEFAULT_CUSTOM_COLOR}
                          onChange={(event) => {
                            const nextColor = event.target.value;
                            setCustomColor(nextColor);
                            setDraft((prev) => ({ ...prev, color: nextColor }));
                          }}
                          className="h-9 p-1"
                        />
                      )}
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">Data Sources</label>
                  <div className="grid grid-cols-2 gap-2 rounded-lg border border-border/70 p-3">
                    {metricOptions.map((metric) => (
                      <label key={metric} className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={draft.metrics.includes(metric)}
                          onCheckedChange={(checked) => toggleMetric(metric, Boolean(checked))}
                        />
                        <span className="text-foreground">{metricConfig[metric].label}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button type="button" onClick={handleSave}>
                    Save
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Export chart image"
            onClick={() => {
              if (chartRef.current) {
                void exportChartAsImage(chartRef.current, config.title);
              }
            }}
            className="h-8 w-8"
          >
            <Download className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Remove chart"
            onClick={() => onRemove(config.id)}
            className="h-8 w-8 text-destructive hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
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
                width={56}
              />
              <Tooltip content={<ChartTooltip />} />
              {config.metrics.map((metric, metricIndex) => (
                <Line
                  key={`${config.id}-${metric}`}
                  type="monotone"
                  dataKey={metric}
                  stroke={metricIndex === 0 ? config.color : metricConfig[metric].color}
                  strokeWidth={2.2}
                  dot={false}
                  activeDot={{ r: 4, fill: metricIndex === 0 ? config.color : metricConfig[metric].color }}
                  isAnimationActive
                  animationDuration={400}
                  animationEasing="ease-out"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

interface HistoricalChartsProps {
  data: SensorData[];
  addChartSignal?: number;
}

export const HistoricalCharts: React.FC<HistoricalChartsProps> = ({ data, addChartSignal }) => {
  const { timezone, isDarkMode } = useApp();
  const [charts, setCharts] = useState<ChartConfig[]>(() => [createDefaultChart()]);
  const previousAddSignal = useRef<number | undefined>(addChartSignal);

  const addChart = () => {
    setCharts((prev) => [...prev, createDefaultChart(`Chart ${prev.length + 1}`)]);
  };

  useEffect(() => {
    if (addChartSignal === undefined) return;
    if (previousAddSignal.current === undefined) {
      previousAddSignal.current = addChartSignal;
      return;
    }
    if (addChartSignal !== previousAddSignal.current) {
      addChart();
      previousAddSignal.current = addChartSignal;
    }
  }, [addChartSignal]);

  const updateChart = (id: string, updates: Partial<ChartConfig>) => {
    setCharts((prev) => prev.map((chart) => (chart.id === id ? { ...chart, ...updates } : chart)));
  };

  const moveChart = (id: string, direction: "up" | "down") => {
    setCharts((prev) => {
      const currentIndex = prev.findIndex((chart) => chart.id === id);
      if (currentIndex < 0) return prev;
      const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
      if (targetIndex < 0 || targetIndex >= prev.length) return prev;
      const next = [...prev];
      [next[currentIndex], next[targetIndex]] = [next[targetIndex], next[currentIndex]];
      return next;
    });
  };

  const removeChart = (id: string) => {
    setCharts((prev) => prev.filter((chart) => chart.id !== id));
  };

  return (
    <div className="space-y-4">
      {charts.length === 0 ? (
        <div className="flex min-h-[340px] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border/70 bg-background p-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border/70 bg-card">
            <LineChartIcon className="h-7 w-7 text-muted-foreground" />
          </div>
          <div className="space-y-1">
            <p className="text-base font-semibold text-foreground">No charts added</p>
            <p className="text-sm text-muted-foreground">Create a new chart to start visualizing sensor data.</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addChart}
            className="btn-panel"
          >
            <Plus className="h-4 w-4" />
            Create Chart
          </Button>
        </div>
      ) : (
        charts.map((chart, index) => (
          <ChartCard
            key={chart.id}
            config={chart}
            data={data}
            timezone={timezone}
            isDarkMode={isDarkMode}
            index={index}
            total={charts.length}
            onUpdate={updateChart}
            onMove={moveChart}
            onRemove={removeChart}
          />
        ))
      )}
    </div>
  );
};

