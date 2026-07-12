import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SensorHistoryPanel } from "@/components/SensorHistoryPanel";

const mockUseStationData = vi.fn();
const mockUsePreferences = vi.fn();

vi.mock("@/contexts/AppContext", () => ({
  useStationData: () => mockUseStationData(),
  usePreferences: () => mockUsePreferences(),
}));

vi.mock("@/components/HistoricalCharts", () => ({
  HistoricalCharts: () => <div data-testid="historical-charts" />,
}));

vi.mock("@/components/RawDataTable", () => ({
  RawDataTable: () => <div data-testid="raw-data-table" />,
}));

describe("SensorHistoryPanel", () => {
  beforeEach(() => {
    mockUseStationData.mockReset();
    mockUseStationData.mockReturnValue({
      historicalData: [],
      historicalDataError: false,
      setHistoryWindowHours: vi.fn(),
    });
    mockUsePreferences.mockReset();
    mockUsePreferences.mockReturnValue({
      timezone: "UTC",
    });
  });

  it("renders the charts and raw data table", () => {
    render(<SensorHistoryPanel />);

    expect(screen.getByTestId("historical-charts")).toBeInTheDocument();
    expect(screen.getByTestId("raw-data-table")).toBeInTheDocument();
  });

  it("leaves only the date-picker control (no Add Chart)", () => {
    render(<SensorHistoryPanel />);

    expect(screen.queryByRole("button", { name: /add chart/i })).not.toBeInTheDocument();
    // The date-picker trigger is the sole remaining control in the panel header.
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});
