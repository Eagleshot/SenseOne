import { describe, expect, it } from "vitest";

import { parseCurrentWeather, parseForecast } from "./weather";

describe("weather api parsing", () => {
  it("parses current weather into display-ready values", () => {
    const parsed = parseCurrentWeather({
      main: { temp: 11.24, feels_like: 9.8, humidity: 81, pressure: 1015 },
      wind: { speed: 2.5, deg: 90 },
      visibility: 7500,
      sys: { sunrise: 1_700_000_000, sunset: 1_700_036_000 },
      weather: [{ description: "light rain", main: "Rain", icon: "10d" }],
      dt: 1_700_010_000,
      timezone: 3600,
      name: "Test City",
    });

    expect(parsed).toMatchObject({
      temperature: 11.2,
      feelsLike: 9.8,
      humidity: 81,
      pressure: 1015,
      visibilityKm: 7.5,
      windSpeedKmh: 9,
      windDirection: 90,
      main: "Rain",
      cityName: "Test City",
    });
  });

  it("groups forecast rows by local day", () => {
    const forecast = parseForecast(
      {
        city: { timezone: 0 },
        list: [
          { dt: 1_700_000_000, main: { temp_min: 2, temp_max: 5 }, weather: [{ icon: "01d" }] },
          { dt: 1_700_003_600, main: { temp_min: 1, temp_max: 8 }, weather: [{ icon: "01d" }] },
        ],
      },
      0
    );

    expect(forecast).toHaveLength(1);
    expect(forecast[0]).toMatchObject({ tempMin: 1, tempMax: 8 });
  });
});
