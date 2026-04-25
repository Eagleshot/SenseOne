import { useEffect, useMemo, useState } from "react";

import { motion } from "framer-motion";
import { Thermometer, Droplets, Wind, Gauge, Eye, Sunrise, Sunset, Navigation, CloudOff } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

import { useApp } from "@/contexts/useApp";
import { isAbortError, stationUrl } from "@/lib/apiClient";
import { LOADING_LABEL, UNAVAILABLE_LABEL } from "@/lib/placeholders";
import { cn } from "@/lib/utils";
import { baseWeatherTheme, resolveWeatherTheme } from "@/lib/weatherThemes";

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

const OPEN_WEATHER_URL = "https://openweathermap.org/";

const makeOffsetFormatter = (options: Intl.DateTimeFormatOptions) =>
  (timestamp: Date, offsetSeconds: number) =>
    new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...options }).format(
      new Date(timestamp.getTime() + offsetSeconds * 1000)
    );

const formatTimeLabelWithOffset = makeOffsetFormatter({ hour: "2-digit", minute: "2-digit", hour12: false });
const formatDateKeyWithOffset = makeOffsetFormatter({ year: "numeric", month: "2-digit", day: "2-digit" });
const formatDayLabelWithOffset = makeOffsetFormatter({ weekday: "short" });

const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

type CurrentWeatherResponse = {
  main?: { temp?: number; feels_like?: number; humidity?: number; pressure?: number };
  wind?: { speed?: number; deg?: number };
  visibility?: number;
  sys?: { sunrise?: number; sunset?: number };
  weather?: { description?: string; main?: string; icon?: string }[];
  dt?: number;
  timezone?: number;
  name?: string;
};

const parseCurrentWeather = (data: CurrentWeatherResponse): WeatherState | null => {
  const temp = data.main?.temp;
  const feelsLike = data.main?.feels_like;
  const humidity = data.main?.humidity;
  const pressure = data.main?.pressure;
  const windSpeed = data.wind?.speed;
  const sunrise = data.sys?.sunrise;
  const sunset = data.sys?.sunset;
  const dt = data.dt;

  if (
    !isFiniteNumber(temp) ||
    !isFiniteNumber(feelsLike) ||
    !isFiniteNumber(humidity) ||
    !isFiniteNumber(pressure) ||
    !isFiniteNumber(windSpeed) ||
    !isFiniteNumber(sunrise) ||
    !isFiniteNumber(sunset) ||
    !isFiniteNumber(dt)
  ) {
    return null;
  }

  const sunriseDate = new Date(sunrise * 1000);
  const sunsetDate = new Date(sunset * 1000);
  const daylightMinutes = Math.max(0, Math.round((sunset - sunrise) / 60));
  const iconCode = data.weather?.[0]?.icon;
  const timezoneOffsetSeconds = isFiniteNumber(data.timezone) ? data.timezone : 0;
  const isNight = dt < sunrise || dt > sunset;

  return {
    temperature: Math.round(temp * 10) / 10,
    feelsLike: Math.round(feelsLike * 10) / 10,
    humidity,
    pressure,
    visibilityKm: isFiniteNumber(data.visibility)
      ? Math.round((data.visibility / 1000) * 10) / 10
      : undefined,
    windSpeedKmh: Math.round(windSpeed * 3.6 * 10) / 10,
    windDirection: data.wind?.deg ?? 0,
    sunrise: formatTimeLabelWithOffset(sunriseDate, timezoneOffsetSeconds),
    sunset: formatTimeLabelWithOffset(sunsetDate, timezoneOffsetSeconds),
    description: data.weather?.[0]?.description,
    main: data.weather?.[0]?.main,
    iconCode,
    iconUrl: iconCode ? `https://openweathermap.org/img/wn/${iconCode}@4x.png` : undefined,
    cityName: data.name,
    updatedAt: new Date(dt * 1000),
    daylightMinutes,
    isNight,
    timezoneOffsetSeconds,
  };
};

const parseForecast = (forecastData: ForecastResponse, fallbackOffsetSeconds: number): ForecastDay[] => {
  const offsetSeconds = isFiniteNumber(forecastData.city?.timezone)
    ? forecastData.city!.timezone!
    : fallbackOffsetSeconds;
  const todayKey = formatDateKeyWithOffset(new Date(), offsetSeconds);
  const buckets = new Map<
    string,
    { date: Date; min: number; max: number; iconCounts: Map<string, number> }
  >();

  forecastData.list?.forEach((item) => {
    const date = new Date(item.dt * 1000);
    const key = formatDateKeyWithOffset(date, offsetSeconds);
    const tempMin = isFiniteNumber(item.main?.temp_min) ? item.main!.temp_min! : item.main?.temp;
    const tempMax = isFiniteNumber(item.main?.temp_max) ? item.main!.temp_max! : item.main?.temp;
    if (!isFiniteNumber(tempMin) || !isFiniteNumber(tempMax)) return;

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
  return sorted.map(([key, bucket], index) => {
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
};

export const WeatherDetail: React.FC = () => {
  const { activeWebcam, isDarkMode } = useApp();
  const [weather, setWeather] = useState<WeatherState | null>(null);
  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isForecastLoading, setIsForecastLoading] = useState(true);

  useEffect(() => {
    if (!activeWebcam.id) {
      setWeather(null);
      setForecast([]);
      setIsLoading(false);
      setIsForecastLoading(false);
      return;
    }
    let isMounted = true;
    const controller = new AbortController();

    const fetchWeather = async () => {
      // Skip polling while the tab is hidden to avoid wasting OpenWeather quota.
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        return;
      }
      setIsLoading(true);
      setIsForecastLoading(true);
      try {
        const currentUrl = stationUrl(activeWebcam.id, "/weather/current");
        const forecastUrl = stationUrl(activeWebcam.id, "/weather/forecast");

        const [currentResponse, forecastResponse] = await Promise.all([
          fetch(currentUrl, { signal: controller.signal }),
          fetch(forecastUrl, { signal: controller.signal }),
        ]);

        if (!currentResponse.ok) {
          throw new Error(`Weather request failed (${currentResponse.status})`);
        }

        const data = await currentResponse.json();
        if (!isMounted) return;

        const nextWeather = parseCurrentWeather(data);
        if (!nextWeather) {
          if (isMounted) {
            setWeather(null);
            setForecast([]);
          }
          return;
        }

        setWeather(nextWeather);

        if (forecastResponse.ok) {
          const forecastData = (await forecastResponse.json()) as ForecastResponse;
          if (!isMounted) return;
          setForecast(parseForecast(forecastData, nextWeather.timezoneOffsetSeconds ?? 0));
        } else if (isMounted) {
          setForecast([]);
        }
      } catch (err) {
        if (isAbortError(err)) return;
        if (isMounted) {
          setWeather(null);
          setForecast([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
          setIsForecastLoading(false);
        }
      }
    };

    fetchWeather();
    const interval = setInterval(fetchWeather, 5 * 60 * 1000);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") fetchWeather();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      isMounted = false;
      controller.abort();
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [activeWebcam.id]);

  const updatedLabel = useMemo(() => {
    if (isLoading) return LOADING_LABEL;
    if (!weather) return "Updated unavailable.";
    const relative = formatDistanceToNow(weather.updatedAt, { addSuffix: true })
      .replace("about ", "")
      .replace(/minutes?/g, "min.");
    return `Updated ${relative}.`;
  }, [isLoading, weather]);

  const daylightLabel = useMemo(() => {
    if (isLoading) return LOADING_LABEL;
    if (weather?.daylightMinutes === undefined) return UNAVAILABLE_LABEL;
    const hours = Math.floor(weather.daylightMinutes / 60);
    const mins = weather.daylightMinutes % 60;
    return `${hours} h ${mins} m`;
  }, [isLoading, weather?.daylightMinutes]);

  const descriptionLabel = isLoading ? LOADING_LABEL : weather?.description || UNAVAILABLE_LABEL;
  const mainLabel = isLoading ? LOADING_LABEL : weather?.main || UNAVAILABLE_LABEL;
  const timeLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : formatTimeLabelWithOffset(weather.updatedAt, weather.timezoneOffsetSeconds ?? 0);
  const temperatureLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : `${weather.temperature} \u00B0C`;
  const feelsLikeLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : `${weather.feelsLike} \u00B0C`;
  const windLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : `${weather.windSpeedKmh} km/h`;
  const windDirection = isLoading || !weather ? 0 : weather.windDirection;
  const windCardinal = useMemo(() => {
    if (isLoading) return LOADING_LABEL;
    if (!weather) return UNAVAILABLE_LABEL;
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(weather.windDirection / 45) % 8];
  }, [isLoading, weather]);
  const humidityLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : `${weather.humidity}%`;
  const pressureLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : `${weather.pressure} hPa`;
  const visibilityLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : weather.visibilityKm === undefined
        ? UNAVAILABLE_LABEL
        : `${weather.visibilityKm} km`;
  const sunriseLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : weather.sunrise;
  const sunsetLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : weather.sunset;
  const showWeatherPlaceholder = !isLoading && !weather;
  const weatherTheme = useMemo(
    () => (weather ? resolveWeatherTheme(weather.main, isDarkMode || (weather.isNight ?? false)) : baseWeatherTheme),
    [weather, isDarkMode],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className={cn("widget-shell-stroke relative overflow-hidden rounded-[28px]", weatherTheme.container)}
    >
      <div className={cn("pointer-events-none absolute inset-0", weatherTheme.overlay)} />
      <div className="relative p-6 sm:p-8 space-y-6">
        <div className={cn("flex items-center justify-end text-sm", weatherTheme.mutedText)}>
          <span>{updatedLabel}</span>
        </div>

        {showWeatherPlaceholder ? (
          <div className="min-h-[24rem] overflow-hidden rounded-[24px] bg-[radial-gradient(circle_at_20%_20%,hsl(var(--primary)/0.18),transparent_42%),radial-gradient(circle_at_80%_0%,hsl(var(--accent)/0.14),transparent_44%),hsl(var(--background))]">
            <div className="pointer-events-none absolute left-8 top-10 h-32 w-32 rounded-full border border-border/40 bg-background/30 blur-2xl" />
            <div className="pointer-events-none absolute right-6 bottom-10 h-44 w-44 rounded-full border border-border/40 bg-background/30 blur-2xl" />
            <div className="flex min-h-[24rem] items-center justify-center">
              <div className="mx-4 max-w-md text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted/50">
                  <CloudOff className="h-7 w-7 text-muted-foreground" />
                </div>
                <p className="text-lg font-semibold text-foreground">No weather data available</p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Try again later or check the backend connection.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center drop-shadow-[0_14px_24px_rgba(0,0,0,0.6)]">
                  {weather?.iconUrl ? (
                    <img
                      src={weather.iconUrl}
                      alt={descriptionLabel}
                      className={cn("h-[150px] w-[150px]", weatherTheme.iconImage)}
                    />
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
                href={OPEN_WEATHER_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={cn("underline underline-offset-2", weatherTheme.linkHover)}
                title={weather?.cityName ? `OpenWeather for ${weather.cityName}` : "OpenWeather"}
              >
                OpenWeather
              </a>
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
};
