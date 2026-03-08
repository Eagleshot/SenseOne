import React, { useEffect, useMemo, useState } from "react";

import { motion } from "framer-motion";
import { Thermometer, Droplets, Wind, Gauge, Eye, Sunrise, Sunset, Navigation } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

import { useApp } from "@/contexts/AppContext";
import { cn } from "@/lib/utils";

type WeatherState = {
  temperature: number;
  feelsLike: number;
  humidity: number;
  pressure: number;
  visibilityKm?: number;
  windSpeedKmh: number;
  windDirection: number;
  sunrise: string;
  sunset: string;
  description?: string;
  main?: string;
  iconCode?: string;
  iconUrl?: string;
  cityId?: number;
  cityName?: string;
  updatedAt: Date;
  daylightMinutes?: number;
  isNight?: boolean;
  timezoneOffsetSeconds?: number;
};

type ForecastDay = {
  dateKey: string;
  label: string;
  iconUrl?: string;
  tempMin: number;
  tempMax: number;
};

type ForecastListItem = {
  dt: number;
  main?: {
    temp_min?: number;
    temp_max?: number;
    temp?: number;
  };
  weather?: { icon?: string }[];
};

type ForecastResponse = {
  list?: ForecastListItem[];
  city?: {
    timezone?: number;
  };
};

const formatTimeLabelWithOffset = (timestamp: Date, offsetSeconds: number) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(timestamp.getTime() + offsetSeconds * 1000));

const formatDateKeyWithOffset = (timestamp: Date, offsetSeconds: number) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(timestamp.getTime() + offsetSeconds * 1000));

const formatDayLabelWithOffset = (timestamp: Date, offsetSeconds: number) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    weekday: "short",
  }).format(new Date(timestamp.getTime() + offsetSeconds * 1000));

export const WeatherDetail: React.FC = () => {
  const { activeWebcam } = useApp();
  const [weather, setWeather] = useState<WeatherState | null>(null);
  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isForecastLoading, setIsForecastLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

  useEffect(() => {
    if (!activeWebcam.id) return;
    let isMounted = true;
    const controller = new AbortController();

    const fetchWeather = async () => {
      setIsLoading(true);
      setIsForecastLoading(true);
      setError(null);
      try {
        const lat = activeWebcam.coordinates.lat;
        const lon = activeWebcam.coordinates.lng;
        const currentUrl = `${apiBaseUrl}/weather/current?lat=${lat}&lon=${lon}&units=metric`;
        const forecastUrl = `${apiBaseUrl}/weather/forecast?lat=${lat}&lon=${lon}&units=metric`;

        const [currentResponse, forecastResponse] = await Promise.all([
          fetch(currentUrl, { signal: controller.signal }),
          fetch(forecastUrl, { signal: controller.signal }),
        ]);

        if (!currentResponse.ok) {
          throw new Error(`Weather request failed (${currentResponse.status})`);
        }

        const data = await currentResponse.json();
        if (!isMounted) return;

        const sunriseDate = new Date(data.sys.sunrise * 1000);
        const sunsetDate = new Date(data.sys.sunset * 1000);
        const daylightMinutes = Math.max(0, Math.round((data.sys.sunset - data.sys.sunrise) / 60));
        const iconCode = data.weather?.[0]?.icon;
        const timezoneOffsetSeconds = typeof data.timezone === "number" ? data.timezone : 0;
        const isNight =
          typeof data.dt === "number" && typeof data.sys?.sunrise === "number" && typeof data.sys?.sunset === "number"
            ? data.dt < data.sys.sunrise || data.dt > data.sys.sunset
            : iconCode?.endsWith("n") ?? false;

        const nextWeather: WeatherState = {
          temperature: Math.round(data.main.temp * 10) / 10,
          feelsLike: Math.round(data.main.feels_like * 10) / 10,
          humidity: data.main.humidity,
          pressure: data.main.pressure,
          visibilityKm:
            typeof data.visibility === "number" ? Math.round((data.visibility / 1000) * 10) / 10 : undefined,
          windSpeedKmh: Math.round(data.wind.speed * 3.6 * 10) / 10,
          windDirection: data.wind.deg ?? 0,
          sunrise: formatTimeLabelWithOffset(sunriseDate, timezoneOffsetSeconds),
          sunset: formatTimeLabelWithOffset(sunsetDate, timezoneOffsetSeconds),
          description: data.weather?.[0]?.description,
          main: data.weather?.[0]?.main,
          iconCode,
          iconUrl: iconCode ? `https://openweathermap.org/img/wn/${iconCode}@4x.png` : undefined,
          cityId: data.id,
          cityName: data.name,
          updatedAt: new Date(data.dt * 1000),
          daylightMinutes,
          isNight,
          timezoneOffsetSeconds,
        };

        setWeather(nextWeather);

        if (forecastResponse.ok) {
          const forecastData = (await forecastResponse.json()) as ForecastResponse;
          const offsetSeconds =
            typeof forecastData.city?.timezone === "number" ? forecastData.city.timezone : timezoneOffsetSeconds;
          const todayKey = formatDateKeyWithOffset(new Date(), offsetSeconds);
          const buckets = new Map<
            string,
            { date: Date; min: number; max: number; iconCounts: Map<string, number> }
          >();

          forecastData.list?.forEach((item) => {
            const date = new Date(item.dt * 1000);
            const key = formatDateKeyWithOffset(date, offsetSeconds);
            const tempMin = typeof item.main?.temp_min === "number" ? item.main.temp_min : item.main?.temp;
            const tempMax = typeof item.main?.temp_max === "number" ? item.main.temp_max : item.main?.temp;
            if (typeof tempMin !== "number" || typeof tempMax !== "number") return;

            if (!buckets.has(key)) {
              buckets.set(key, {
                date,
                min: tempMin,
                max: tempMax,
                iconCounts: new Map(),
              });
            }

            const bucket = buckets.get(key)!;
            bucket.min = Math.min(bucket.min, tempMin);
            bucket.max = Math.max(bucket.max, tempMax);

            const icon = item.weather?.[0]?.icon;
            if (icon) {
              bucket.iconCounts.set(icon, (bucket.iconCounts.get(icon) ?? 0) + 1);
            }
          });

          const sorted = Array.from(buckets.entries()).sort(([a], [b]) => a.localeCompare(b));
          const nextForecast = sorted.map(([key, bucket], index) => {
            const icon = Array.from(bucket.iconCounts.entries()).sort((a, b) => b[1] - a[1])[0]?.[0];
            return {
              dateKey: key,
              label:
                key === todayKey && index === 0
                  ? "Today"
                  : formatDayLabelWithOffset(bucket.date, offsetSeconds),
              iconUrl: icon ? `https://openweathermap.org/img/wn/${icon}@2x.png` : undefined,
              tempMin: Math.round(bucket.min),
              tempMax: Math.round(bucket.max),
            };
          });

          setForecast(nextForecast);
        } else {
          if (isMounted) {
            setForecast([]);
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        if (isMounted) {
          setWeather(null);
          setForecast([]);
          setError("Unable to load live weather data.");
        }
      } finally {
        if (isMounted) setIsLoading(false);
        if (isMounted) setIsForecastLoading(false);
      }
    };

    fetchWeather();
    const interval = setInterval(fetchWeather, 5 * 60 * 1000);

    return () => {
      isMounted = false;
      controller.abort();
      clearInterval(interval);
    };
  }, [activeWebcam.coordinates.lat, activeWebcam.coordinates.lng, activeWebcam.id, apiBaseUrl]);

  const updatedLabel = useMemo(() => {
    if (!weather) return "Updated --.";
    const relative = formatDistanceToNow(weather.updatedAt, { addSuffix: true })
      .replace("about ", "")
      .replace(/minutes?/g, "min.");
    return `Updated ${relative}.`;
  }, [weather]);

  const daylightLabel = useMemo(() => {
    if (weather?.daylightMinutes === undefined) return "--";
    const hours = Math.floor(weather.daylightMinutes / 60);
    const mins = weather.daylightMinutes % 60;
    return `${hours} h ${mins} m`;
  }, [weather?.daylightMinutes]);

  const descriptionLabel = isLoading ? "Loading..." : weather?.description || "--";
  const mainLabel = isLoading ? "Main" : weather?.main || "Main";
  const timeLabel =
    isLoading || !weather
      ? "--"
      : formatTimeLabelWithOffset(weather.updatedAt, weather.timezoneOffsetSeconds ?? 0);
  const temperatureLabel = isLoading || !weather ? "--" : `${weather.temperature} \u00B0C`;
  const feelsLikeLabel = isLoading || !weather ? "--" : `${weather.feelsLike} \u00B0C`;
  const windLabel = isLoading || !weather ? "--" : `${weather.windSpeedKmh} km/h`;
  const windDirection = isLoading || !weather ? 0 : weather.windDirection;
  const windCardinal = useMemo(() => {
    if (isLoading || !weather) return "--";
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(weather.windDirection / 45) % 8];
  }, [isLoading, weather]);
  const humidityLabel = isLoading || !weather ? "--" : `${weather.humidity}%`;
  const pressureLabel = isLoading || !weather ? "--" : `${weather.pressure} hPa`;
  const visibilityLabel = isLoading || !weather ? "--" : `${weather.visibilityKm ?? "--"} km`;
  const sunriseLabel = isLoading || !weather ? "--" : weather.sunrise;
  const sunsetLabel = isLoading || !weather ? "--" : weather.sunset;
  const openWeatherUrl = useMemo(() => "https://openweathermap.org/", []);
  const weatherTheme = useMemo(() => {
    const baseTheme = {
      container:
        "border border-border/70 bg-secondary/90 text-foreground shadow-[0_18px_45px_rgba(0,0,0,0.336)] dark:border-transparent dark:bg-card dark:shadow-[0_24px_60px_rgba(0,0,0,0.54)]",
      overlay:
        "bg-[radial-gradient(circle_at_top,_hsl(var(--primary)/0.18),_transparent_55%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--foreground)/0.08),_transparent_55%)]",
      surface:
        "bg-[hsl(var(--sidebar-background))] shadow-[inset_0_0_0_1px_hsl(var(--border)/0.6)]",
      card:
        "bg-[hsl(var(--sidebar-background))] shadow-[inset_0_0_0_1px_hsl(var(--border)/0.5)]",
      mutedText: "text-muted-foreground",
      foregroundText: "text-foreground",
      divider: "bg-[hsl(var(--muted-foreground))]/60",
      iconMuted: "text-muted-foreground",
      placeholder: "bg-muted/60 dark:bg-muted/50",
      linkHover: "hover:text-foreground",
    };

    if (!weather) return baseTheme;

    const main = weather.main?.toLowerCase() ?? "";
    const isNight = weather.isNight ?? false;
    const isFoggy = ["mist", "fog", "haze", "smoke", "dust", "sand", "ash"].includes(main);
    const isThunder = main === "thunderstorm" || main === "tornado" || main === "squall";
    const isSnow = main === "snow";
    const isClear = main === "clear";

    if (isNight || isFoggy || isThunder) {
      return {
        container:
          "border border-white/10 bg-slate-950/90 text-white shadow-[0_24px_60px_rgba(0,0,0,0.6)]",
        overlay: "bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.08),_transparent_55%)]",
        surface: "bg-white/10 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12)]",
        card: "bg-white/10 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12)]",
        mutedText: "text-white/70",
        foregroundText: "text-white",
        divider: "bg-white/20",
        iconMuted: "text-white/70",
        placeholder: "bg-white/10",
        linkHover: "hover:text-white",
      };
    }

    if (isSnow) {
      return {
        container:
          "border border-border/70 bg-white text-slate-900 shadow-[0_18px_45px_rgba(0,0,0,0.18)]",
        overlay: "bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.9),_transparent_60%)]",
        surface: "bg-white/80 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]",
        card: "bg-white/80 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]",
        mutedText: "text-slate-500",
        foregroundText: "text-slate-900",
        divider: "bg-slate-300/70",
        iconMuted: "text-slate-500",
        placeholder: "bg-slate-200/70",
        linkHover: "hover:text-slate-900",
      };
    }

    if (isClear) {
      return {
        container:
          "border border-sky-400/25 bg-[#0b1d34] text-white shadow-[0_24px_60px_rgba(2,6,23,0.6)]",
        overlay: "bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.35),_transparent_60%)]",
        surface: "bg-sky-500/10 shadow-[inset_0_0_0_1px_rgba(125,211,252,0.18)]",
        card: "bg-sky-500/10 shadow-[inset_0_0_0_1px_rgba(125,211,252,0.18)]",
        mutedText: "text-sky-100/70",
        foregroundText: "text-white",
        divider: "bg-sky-100/20",
        iconMuted: "text-sky-100/70",
        placeholder: "bg-sky-500/15",
        linkHover: "hover:text-white",
      };
    }

    return baseTheme;
  }, [weather]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className={cn("relative overflow-hidden rounded-[28px]", weatherTheme.container)}
    >
      <div className={cn("pointer-events-none absolute inset-0", weatherTheme.overlay)} />
      <div className="relative p-6 sm:p-8 space-y-6">
        <div className={cn("flex items-center justify-end text-sm", weatherTheme.mutedText)}>
          <span>{error ? "Updated --." : updatedLabel}</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center drop-shadow-[0_14px_24px_rgba(0,0,0,0.6)]">
              {weather?.iconUrl ? (
                <img src={weather.iconUrl} alt={descriptionLabel} className="h-[150px] w-[150px]" />
              ) : (
                <Thermometer className={cn("h-[75px] w-[75px]", weatherTheme.iconMuted)} />
              )}
            </div>
            <div>
              <p className={cn("text-sm", weatherTheme.mutedText)}>{timeLabel}</p>
              <p className="text-3xl sm:text-4xl font-semibold">{mainLabel}</p>
              <p className={cn("capitalize", weatherTheme.mutedText)}>{descriptionLabel}</p>
            </div>
          </div>
          <div className="text-left sm:text-right">
            <p className="text-3xl sm:text-4xl font-semibold">{temperatureLabel}</p>
            <p className={cn("", weatherTheme.mutedText)}>Feels like {feelsLikeLabel}</p>
          </div>
        </div>

        <div className={cn("rounded-full px-5 py-3 flex items-center justify-between gap-4", weatherTheme.surface)}>
          <div className={cn("flex items-center gap-2 text-sm", weatherTheme.mutedText)}>
            <Sunrise className="h-4 w-4" />
            <span>{sunriseLabel}</span>
          </div>
          <div className={cn("flex-1 h-px", weatherTheme.divider)} />
          <div className={cn("text-sm", weatherTheme.mutedText)}>{daylightLabel}</div>
          <div className={cn("flex-1 h-px", weatherTheme.divider)} />
          <div className={cn("flex items-center gap-2 text-sm", weatherTheme.mutedText)}>
            <span>{sunsetLabel}</span>
            <Sunset className="h-4 w-4" />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className={cn("rounded-full px-4 py-3 flex items-center justify-between", weatherTheme.surface)}>
            <div className={cn("flex items-center gap-2", weatherTheme.mutedText)}>
              <Wind className="h-4 w-4" />
              <span>Wind</span>
            </div>
            <div className="flex items-center gap-2 text-right">
              <span className={cn("font-semibold", weatherTheme.foregroundText)}>{windLabel}</span>
              <span className={cn("text-xs", weatherTheme.mutedText)}>{windCardinal}</span>
              <Navigation
                className={cn("h-4 w-4 fill-current translate-y-2", weatherTheme.iconMuted)}
                style={{ transform: `rotate(${windDirection}deg)` }}
                aria-label="Wind direction"
              />
            </div>
          </div>
          <div className={cn("rounded-full px-4 py-3 flex items-center justify-between", weatherTheme.surface)}>
            <div className={cn("flex items-center gap-2", weatherTheme.mutedText)}>
              <Droplets className="h-4 w-4" />
              <span>Humidity</span>
            </div>
            <span className={cn("font-semibold", weatherTheme.foregroundText)}>{humidityLabel}</span>
          </div>
          <div className={cn("rounded-full px-4 py-3 flex items-center justify-between", weatherTheme.surface)}>
            <div className={cn("flex items-center gap-2", weatherTheme.mutedText)}>
              <Gauge className="h-4 w-4" />
              <span>Pressure</span>
            </div>
            <span className={cn("font-semibold", weatherTheme.foregroundText)}>{pressureLabel}</span>
          </div>
          <div className={cn("rounded-full px-4 py-3 flex items-center justify-between", weatherTheme.surface)}>
            <div className={cn("flex items-center gap-2", weatherTheme.mutedText)}>
              <Eye className="h-4 w-4" />
              <span>Visibility</span>
            </div>
            <span className={cn("font-semibold", weatherTheme.foregroundText)}>{visibilityLabel}</span>
          </div>
        </div>

        <div className="grid w-full grid-cols-[repeat(auto-fit,minmax(110px,1fr))] gap-3">
          {isForecastLoading && forecast.length === 0 ? (
            <div className={cn("col-span-full text-center text-xs", weatherTheme.mutedText)}>Loading forecast...</div>
          ) : forecast.length === 0 ? (
            <div className={cn("col-span-full text-center text-xs", weatherTheme.mutedText)}>No forecast available.</div>
          ) : (
            forecast.map((day: ForecastDay) => (
              <div
                key={day.dateKey}
                className={cn(
                  "rounded-2xl px-3 py-4 flex flex-col items-center gap-2 text-center",
                  weatherTheme.card
                )}
              >
                <span className={cn("text-xs", weatherTheme.mutedText)}>{day.label}</span>
                {day.iconUrl ? (
                  <img src={day.iconUrl} alt={day.label} className="h-10 w-10" />
                ) : (
                  <div className={cn("h-10 w-10 rounded-full", weatherTheme.placeholder)} />
                )}
                <div className={cn("text-lg font-semibold", weatherTheme.foregroundText)}>{`${day.tempMax}\u00B0`}</div>
                <div className={cn("text-xs", weatherTheme.mutedText)}>{`${day.tempMin}\u00B0`}</div>
              </div>
            ))
          )}
        </div>

        <div className={cn("text-xs text-right", weatherTheme.mutedText)}>
          Data by{" "}
          <a
            href={openWeatherUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn("underline underline-offset-2", weatherTheme.linkHover)}
            title={weather?.cityName ? `OpenWeather for ${weather.cityName}` : "OpenWeather"}
          >
            OpenWeather
          </a>
        </div>
      </div>
    </motion.div>
  );
};
