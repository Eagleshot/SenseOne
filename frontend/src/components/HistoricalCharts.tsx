import { useEffect, useMemo, useRef, useState } from "react";

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
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { formatDateTimeLabel, formatTimeLabel } from "@/lib/datetime";
import { TEMPERATURE_UNIT } from "@/lib/units";
import { useApp } from "@/contexts/AppContext";
import type { SensorData } from "@/data/types";
import { exportChartAsImage } from "./historicalChartExport";
import type { ChartIconKey, MetricType } from "./historicalChartUtils";

type ChartConfig = {
  id: string;
  title: string;
  icon: ChartIconKey;
  color: string;
  metrics: MetricType[];
};

type ChartDraft = Omit<ChartConfig, "id">;

const metricConfig: Record<MetricType, { label: string; unit: string; color: string }> = {
  temperature: { label: "Temperature", unit: TEMPERATURE_UNIT, color: "hsl(var(--chart-1))" },
  battery: { label: "Battery Level", unit: "%", color: "hsl(var(--chart-2))" },
  humidity: { label: "Humidity", unit: "%", color: "hsl(var(--chart-3))" },
  windSpeed: { label: "Wind Speed", unit: "km/h", color: "hsl(var(--chart-1))" },
  pressure: { label: "Pressure", unit: "hPa", color: "hsl(var(--chart-2))" },
  visibility: { label: "Visibility", unit: "km", color: "hsl(var(--chart-3))" },
  uvIndex: { label: "UV Index", unit: "", color: "hsl(var(--chart-1))" },
  dewPoint: { label: "Dew Point", unit: TEMPERATURE_UNIT, color: "hsl(var(--chart-2))" },
  feelsLike: { label: "Feels Like", unit: TEMPERATURE_UNIT, color: "hsl(var(--chart-3))" },
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

const ADD_CHART_LABEL = "Add Chart";
const CHART_SETTINGS_LABEL = "Chart Settings";

const getAutoChartTitle = (metrics: MetricType[]) =>
  metrics.map((metric) => metricConfig[metric].label).join(" + ") || "Custom Chart";
const chartThemeColorOptions = [
  { value: "hsl(var(--chart-1))", label: "Theme Chart 1" },
  { value: "hsl(var(--chart-2))", label: "Theme Chart 2" },
  { value: "hsl(var(--chart-3))", label: "Theme Chart 3" },
] as const;
type ChartThemeColorValue = (typeof chartThemeColorOptions)[number]["value"];
type ChartColorSelection = ChartThemeColorValue | "custom";

const createChartId = () => `chart-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const ALL_METRICS: MetricType[] = [
  "temperature",
  "battery",
  "humidity",
  "windSpeed",
  "pressure",
  "visibility",
  "uvIndex",
  "dewPoint",
  "feelsLike",
];

const getDefaultMetrics = (): MetricType[] => ["temperature"];

const orderMetrics = (selectedMetrics: MetricType[]) =>
  ALL_METRICS.filter((metric) => selectedMetrics.includes(metric));

const createDefaultChart = (): ChartConfig => ({
  id: createChartId(),
  title: getAutoChartTitle(getDefaultMetrics()),
  icon: "line",
  color: chartThemeColorOptions[0].value,
  metrics: getDefaultMetrics(),
});

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

type ChartCardProps = {
  config: ChartConfig;
  data: SensorData[];
  timezone: string;
  isDarkMode: boolean;
  isSettingsOpen: boolean;
  index: number;
  total: number;
  onSettingsOpenChange: (open: boolean) => void;
  onUpdate: (id: string, updates: Partial<ChartConfig>) => void;
  onMove: (id: string, direction: "up" | "down") => void;
  onRemove: (id: string) => void;
};

const ChartCard: React.FC<ChartCardProps> = ({
  config,
  data,
  timezone,
  isDarkMode,
  isSettingsOpen,
  index,
  total,
  onSettingsOpenChange,
  onUpdate,
  onMove,
  onRemove,
}) => {
  const Icon = chartIconConfig[config.icon];
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState<ChartDraft>({
    title: config.title,
    icon: config.icon,
    color: config.color,
    metrics: config.metrics,
  });
  const [metricsDropdownOpen, setMetricsDropdownOpen] = useState(false);
  const [colorSelection, setColorSelection] = useState<ChartColorSelection>(() => getColorSelection(config.color));
  const [customColor, setCustomColor] = useState<string>(
    isValidHexColor(config.color) ? config.color : DEFAULT_CUSTOM_COLOR
  );

  useEffect(() => {
    if (!isSettingsOpen) return;
    setDraft({
      title: config.title,
      icon: config.icon,
      color: config.color,
      metrics: config.metrics,
    });
    setColorSelection(getColorSelection(config.color));
    setCustomColor(isValidHexColor(config.color) ? config.color : DEFAULT_CUSTOM_COLOR);
    setMetricsDropdownOpen(false);
  }, [config, isSettingsOpen]);

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

  const handleMetricToggle = (metric: MetricType, checked: boolean | "indeterminate") => {
    setDraft((prev) => {
      const currentAutoTitle = getAutoChartTitle(prev.metrics);

      if (checked === true) {
        const nextMetrics = orderMetrics([...prev.metrics, metric]);
        return {
          ...prev,
          title: prev.title === currentAutoTitle ? getAutoChartTitle(nextMetrics) : prev.title,
          metrics: nextMetrics,
        };
      }

      const nextMetrics = prev.metrics.filter((item) => item !== metric);
      if (nextMetrics.length === 0) {
        return prev;
      }

      return {
        ...prev,
        title: prev.title === currentAutoTitle ? getAutoChartTitle(nextMetrics) : prev.title,
        metrics: orderMetrics(nextMetrics),
      };
    });
  };

  const handleSave = () => {
    const nextColor =
      colorSelection === "custom" ? (isValidHexColor(customColor) ? customColor : DEFAULT_CUSTOM_COLOR) : draft.color;
    const nextMetrics = draft.metrics.length > 0 ? orderMetrics(draft.metrics) : getDefaultMetrics();
    onUpdate(config.id, {
      title: draft.title.trim() || getAutoChartTitle(nextMetrics),
      icon: draft.icon,
      color: nextColor,
      metrics: nextMetrics,
    });
    onSettingsOpenChange(false);
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

  const yAxisUnit = useMemo(() => {
    const units = Array.from(new Set(config.metrics.map((metric) => metricConfig[metric].unit).filter(Boolean)));
    return units.length === 1 ? units[0] : "";
  }, [config.metrics]);
  const metricsLabel = useMemo(
    () => config.metrics.map((metric) => metricConfig[metric].label).join(" + "),
    [config.metrics]
  );

  const formatYAxisTick = (value: number | string) => {
    if (!yAxisUnit) return `${value}`;
    return `${value} ${yAxisUnit}`;
  };

  return (
    <div className="widget-shell-stroke rounded-2xl border border-border bg-card/70 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-2xl font-bold text-foreground">{config.title}</h2>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Move chart up"
            disabled={index === 0}
            onClick={() => onMove(config.id, "up")}
            className="btn-icon-panel h-8 w-8"
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
            className="btn-icon-panel h-8 w-8"
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
          <Dialog open={isSettingsOpen} onOpenChange={onSettingsOpenChange}>
            <DialogTrigger asChild>
              <Button type="button" variant="ghost" size="icon" aria-label={CHART_SETTINGS_LABEL} className="btn-icon-panel h-8 w-8">
                <Settings2 className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{CHART_SETTINGS_LABEL}</DialogTitle>
                <DialogDescription>
                  Configure the selected chart title, metrics, icon, and color.
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
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">Metrics</label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setMetricsDropdownOpen(!metricsDropdownOpen)}
                      className="inline-flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <span className="text-left">
                        {draft.metrics.length > 0
                          ? draft.metrics.map((m) => metricConfig[m].label).join(", ")
                          : "Select metrics..."}
                      </span>
                      <span className="ml-2 opacity-50">â–¼</span>
                    </button>
                    {metricsDropdownOpen && (
                      <div className="absolute z-50 mt-1 w-full rounded-md border border-input bg-popover shadow-md">
                        {ALL_METRICS.map((metric, index) => (
                          <label
                            key={metric}
                            className={`flex items-center gap-3 px-3 py-2 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground transition-colors ${
                              index < ALL_METRICS.length - 1 ? 'border-b border-border/50' : ''
                            }`}
                          >
                            <Checkbox
                              checked={draft.metrics.includes(metric)}
                              onCheckedChange={(checked) => handleMetricToggle(metric, checked)}
                              disabled={draft.metrics.length === 1 && draft.metrics.includes(metric)}
                            />
                            <span className="flex flex-1 items-center justify-between gap-2">
                              <span className="font-medium text-foreground">{metricConfig[metric].label}</span>
                              <span className="text-xs text-muted-foreground">{metricConfig[metric].unit || "Value"}</span>
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
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
                void exportChartAsImage(chartRef.current, {
                  title: config.title,
                  subtitle: metricsLabel,
                });
              }
            }}
            className="btn-icon-panel h-8 w-8"
          >
            <Download className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Remove chart"
            onClick={() => onRemove(config.id)}
            className="btn-icon-panel h-8 w-8 text-destructive hover:text-destructive"
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
                tickFormatter={formatYAxisTick}
                width={72}
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
  activeStationId: string;
  data: SensorData[];
  addChartSignal?: number;
}

export const HistoricalCharts: React.FC<HistoricalChartsProps> = ({
  activeStationId,
  data,
  addChartSignal,
}) => {
  const { timezone, isDarkMode } = useApp();
  const [charts, setCharts] = useState<ChartConfig[]>([]);
  const [activeSettingsChartId, setActiveSettingsChartId] = useState<string | null>(null);
  const previousAddSignal = useRef<number | undefined>(addChartSignal);
  const previousStationId = useRef(activeStationId);

  const addChart = () => {
    const nextChart = createDefaultChart();
    setCharts((prev) => [...prev, nextChart]);
    setActiveSettingsChartId(nextChart.id);
  };

  useEffect(() => {
    if (activeStationId === previousStationId.current) return;

    setCharts([]);
    setActiveSettingsChartId(null);
    previousAddSignal.current = addChartSignal;
    previousStationId.current = activeStationId;
  }, [activeStationId, addChartSignal]);

  useEffect(() => {
    if (addChartSignal === undefined) return;
    if (previousAddSignal.current === undefined) {
      previousAddSignal.current = addChartSignal;
      return;
    }
    if (addChartSignal !== previousAddSignal.current) {
      const nextChart = createDefaultChart();
      setCharts((prev) => [...prev, nextChart]);
      setActiveSettingsChartId(nextChart.id);
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
    setActiveSettingsChartId((currentId) => (currentId === id ? null : currentId));
    setCharts((prev) => prev.filter((chart) => chart.id !== id));
  };

  return (
    <div className="space-y-4">
      {charts.length === 0 ? (
        <div className="flex min-h-[340px] flex-col items-center justify-center gap-4 rounded-2xl bg-background p-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border/70 bg-card">
            <LineChartIcon className="h-7 w-7 text-muted-foreground" />
          </div>
          <div className="space-y-1">
            <p className="text-base font-semibold text-foreground">No charts added</p>
            <p className="text-sm text-muted-foreground">
              Create a new chart to start visualizing sensor data.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addChart}
            className="btn-panel"
          >
              <Plus className="h-4 w-4" />
              {ADD_CHART_LABEL}
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
            isSettingsOpen={activeSettingsChartId === chart.id}
            index={index}
            total={charts.length}
            onSettingsOpenChange={(open) =>
              setActiveSettingsChartId((currentId) => (open ? chart.id : currentId === chart.id ? null : currentId))
            }
            onUpdate={updateChart}
            onMove={moveChart}
            onRemove={removeChart}
          />
        ))
      )}
    </div>
  );
};

