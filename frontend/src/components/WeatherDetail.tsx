import { useMemo } from "react";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Thermometer, Droplets, Wind, Gauge, Eye, Sunrise, Sunset, Navigation, CloudOff } from "lucide-react";

import { fetchStationWeather, type ForecastDay } from "@/api/weather";
import { usePreferences, useStationData } from "@/contexts/AppContext";
import { apiBaseUrl } from "@/lib/apiClient";
import { formatRelativeShort, formatTimeLabel } from "@/lib/datetime";
import { LOADING_LABEL, UNAVAILABLE_LABEL } from "@/lib/placeholders";
import { cn } from "@/lib/utils";
import { baseWeatherTheme, resolveWeatherTheme } from "@/lib/weatherThemes";

const OPEN_WEATHER_URL = "https://openweathermap.org/";

export const WeatherDetail: React.FC = () => {
  const { activeWebcam } = useStationData();
  // The shared display timezone (by default the station's own), so weather
  // times agree with the image timeline and charts.
  const { isDarkMode, timezone } = usePreferences();

  // Current weather + forecast for the active station. Polls every 5 minutes;
  // react-query pauses the interval while the tab is hidden (OpenWeather quota)
  // and refetches on refocus. Upstream failures land in `isError` -> placeholder.
  const weatherQuery = useQuery({
    queryKey: ["station-weather", activeWebcam.id],
    enabled: Boolean(activeWebcam.id),
    queryFn: ({ signal }) => fetchStationWeather(apiBaseUrl, activeWebcam.id, signal),
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
  });
  const weather = weatherQuery.data?.weather ?? null;
  const forecast = weatherQuery.data?.forecast ?? [];
  // True only during the first fetch for a station; background refetches keep
  // showing the previous values instead of flashing the loading labels.
  const isLoading = weatherQuery.isLoading;
  const isForecastLoading = isLoading;

  const updatedLabel = useMemo(() => {
    if (isLoading) return LOADING_LABEL;
    if (!weather) return "Updated unavailable.";
    return `Updated ${formatRelativeShort(weather.updatedAt)}.`;
  }, [isLoading, weather]);

  const daylightLabel = isLoading
    ? LOADING_LABEL
    : weather?.daylightMinutes === undefined
      ? UNAVAILABLE_LABEL
      : `${Math.floor(weather.daylightMinutes / 60)} h ${weather.daylightMinutes % 60} m`;

  const descriptionLabel = isLoading ? LOADING_LABEL : weather?.description || UNAVAILABLE_LABEL;
  const mainLabel = isLoading ? LOADING_LABEL : weather?.main || UNAVAILABLE_LABEL;
  const timeLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : formatTimeLabel(weather.updatedAt, timezone);
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
      : formatTimeLabel(weather.sunriseAt, timezone);
  const sunsetLabel =
    isLoading || !weather
      ? isLoading ? LOADING_LABEL : UNAVAILABLE_LABEL
      : formatTimeLabel(weather.sunsetAt, timezone);
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
                <CloudOff className="mx-auto mb-4 h-7 w-7 text-muted-foreground" />
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

