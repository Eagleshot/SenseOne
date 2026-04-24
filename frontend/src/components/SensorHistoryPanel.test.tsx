import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SensorHistoryPanel } from "@/components/SensorHistoryPanel";

const mockUseApp = vi.fn();

vi.mock("@/contexts/useApp", () => ({
  useApp: () => mockUseApp(),
}));

vi.mock("@/components/HistoricalCharts", () => ({
  HistoricalCharts: () => <div data-testid="historical-charts" />,
}));

vi.mock("@/components/RawDataTable", () => ({
  RawDataTable: () => <div data-testid="raw-data-table" />,
}));

describe("SensorHistoryPanel", () => {
  beforeEach(() => {
    mockUseApp.mockReset();
    mockUseApp.mockReturnValue({
      activeWebcam: { id: "station-1" },
      historicalData: [],
      timezone: "UTC",
    });
  });

  it("renders the Add Chart button as always enabled", () => {
    render(<SensorHistoryPanel />);

    expect(screen.getByRole("button", { name: /add chart/i })).toBeEnabled();
  });
});
