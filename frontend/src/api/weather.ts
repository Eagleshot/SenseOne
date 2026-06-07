import { stationPath } from "@/api/stations";

export type WeatherState = {
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

export type ForecastDay = {
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

const makeOffsetFormatter = (options: Intl.DateTimeFormatOptions) =>
  (timestamp: Date, offsetSeconds: number) =>
    new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...options }).format(
      new Date(timestamp.getTime() + offsetSeconds * 1000)
    );

export const formatTimeLabelWithOffset = makeOffsetFormatter({ hour: "2-digit", minute: "2-digit", hour12: false });
const formatDateKeyWithOffset = makeOffsetFormatter({ year: "numeric", month: "2-digit", day: "2-digit" });
const formatDayLabelWithOffset = makeOffsetFormatter({ weekday: "short" });

const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

export const parseCurrentWeather = (data: CurrentWeatherResponse): WeatherState | null => {
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

export const parseForecast = (forecastData: ForecastResponse, fallbackOffsetSeconds: number): ForecastDay[] => {
  const offsetSeconds = isFiniteNumber(forecastData.city?.timezone)
    ? forecastData.city!.timezone!
    : fallbackOffsetSeconds;
  const todayKey = formatDateKeyWithOffset(new Date(), offsetSeconds);
  const buckets = new Map<
    string,
    { date: Date; min: number; max: number; iconCounts: Map<string, number> }
  >();

  forecastData.list?.forEach((item) => {
    if (!isFiniteNumber(item.dt)) return;  // skip entries with a missing/invalid timestamp
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

  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, bucket], index) => {
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

export const fetchStationWeather = async (
  apiBaseUrl: string,
  stationId: string,
  signal?: AbortSignal
): Promise<{ weather: WeatherState | null; forecast: ForecastDay[] }> => {
  const [currentResponse, forecastResponse] = await Promise.all([
    fetch(stationPath(stationId, "/weather/current", apiBaseUrl), { signal }),
    fetch(stationPath(stationId, "/weather/forecast", apiBaseUrl), { signal }),
  ]);

  if (!currentResponse.ok) {
    throw new Error(`Weather request failed (${currentResponse.status})`);
  }

  const currentData = await currentResponse.json();
  const weather = parseCurrentWeather(currentData);
  if (!weather) return { weather: null, forecast: [] };

  if (!forecastResponse.ok) return { weather, forecast: [] };
  const forecastData = (await forecastResponse.json()) as ForecastResponse;
  return {
    weather,
    forecast: parseForecast(forecastData, weather.timezoneOffsetSeconds ?? 0),
  };
};

