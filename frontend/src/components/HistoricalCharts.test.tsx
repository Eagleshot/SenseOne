import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { HistoricalCharts } from "@/components/HistoricalCharts";

const mockUseApp = vi.fn();

vi.mock("@/contexts/AppContext", () => ({
  useApp: () => mockUseApp(),
}));

vi.mock("recharts", () => {
  const Wrapper = ({ children }: { children?: ReactNode }) => <div>{children}</div>;

  return {
    ResponsiveContainer: Wrapper,
    ComposedChart: Wrapper,
    CartesianGrid: () => null,
    Tooltip: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Line: ({ dataKey }: { dataKey: string }) => <div data-key={dataKey} data-testid="chart-line" />,
  };
});

const data = [
  {
    timestamp: new Date("2026-01-02T10:00:00Z"),
    temperature: 21,
    humidity: 45,
    pressure: 1012,
    battery: 88,
    windSpeed: 10,
    windDirection: 180,
    visibility: 8,
    uvIndex: 2,
    dewPoint: 10,
    feelsLike: 21,
  },
];

describe("HistoricalCharts", () => {
  beforeEach(() => {
    mockUseApp.mockReset();
    mockUseApp.mockReturnValue({
      timezone: "UTC",
      isDarkMode: false,
    });
  });

  it("opens chart settings for a newly added chart and resets the chart list when the active station changes", async () => {
    const { rerender } = render(
      <HistoricalCharts
        activeStationId="station-1"
        addChartSignal={0}
        data={data}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /add chart/i }));

    expect(screen.getByText("Chart Settings")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Temperature")).toBeInTheDocument();

    rerender(
      <HistoricalCharts
        activeStationId="station-2"
        addChartSignal={0}
        data={data}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("No charts added")).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: /temperature/i })).not.toBeInTheDocument();
  });

  it("opens chart settings when a chart is added through the header signal", async () => {
    const { rerender } = render(
      <HistoricalCharts
        activeStationId="station-1"
        addChartSignal={0}
        data={data}
      />
    );

    rerender(
      <HistoricalCharts
        activeStationId="station-1"
        addChartSignal={1}
        data={data}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Chart Settings")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("Temperature")).toBeInTheDocument();
  });

  it("lets you choose individual metrics for a chart", async () => {
    render(
      <HistoricalCharts
        activeStationId="station-1"
        addChartSignal={0}
        data={data}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /add chart/i }));

    await waitFor(() => {
      expect(screen.getByText("Chart Settings")).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue("Temperature")).toBeInTheDocument();
    expect(screen.getAllByTestId("chart-line")).toHaveLength(1);

    // Open metrics dropdown and select humidity
    fireEvent.click(screen.getAllByRole("button", { name: /Temperature/ })[0]);
    await waitFor(() => {
      fireEvent.click(screen.getByRole("checkbox", { name: /humidity/i }));
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(screen.getAllByTestId("chart-line")).toHaveLength(2);
    });
    expect(screen.getByRole("heading", { name: /temperature \+ humidity/i })).toBeInTheDocument();
  });
});

