import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SensorHistoryPanel } from "@/components/SensorHistoryPanel";

const mockUseStationData = vi.fn();
const mockUsePreferences = vi.fn();
const mockSetHistoryWindowHours = vi.fn();

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
      setHistoryWindowHours: mockSetHistoryWindowHours,
    });
    mockSetHistoryWindowHours.mockReset();
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

  it("integrates relative and absolute ranges and reflects a relative selection in the trigger", async () => {
    render(<SensorHistoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: /select data range/i }));
    expect(await screen.findByText("Relative")).toBeInTheDocument();
    expect(screen.getByText("Absolute")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Last 30 days" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Last year" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Last 6 h" }));

    expect(mockSetHistoryWindowHours).toHaveBeenCalledWith(24);
    expect(screen.getByRole("button", { name: /current range: last 6 h/i })).toBeInTheDocument();
  });

  it("applies absolute edits together", async () => {
    render(<SensorHistoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: /select data range/i }));
    await screen.findByText("Absolute");
    fireEvent.change(screen.getByLabelText("From time"), { target: { value: "08:00" } });

    expect(mockSetHistoryWindowHours).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Apply range" }));
    expect(mockSetHistoryWindowHours).toHaveBeenCalledTimes(1);
  });
});
