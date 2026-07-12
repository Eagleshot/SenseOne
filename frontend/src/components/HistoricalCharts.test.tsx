import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { HistoricalCharts } from "@/components/HistoricalCharts";

const mockUsePreferences = vi.fn();

vi.mock("@/contexts/AppContext", () => ({
  usePreferences: () => mockUsePreferences(),
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
  },
];

describe("HistoricalCharts", () => {
  beforeEach(() => {
    mockUsePreferences.mockReset();
    mockUsePreferences.mockReturnValue({
      timezone: "UTC",
      isDarkMode: false,
    });
  });

  it("auto-renders one plot per numeric metric", () => {
    render(<HistoricalCharts data={data} />);

    expect(screen.getAllByTestId("chart-line")).toHaveLength(4);
    expect(screen.getByRole("heading", { name: /^temperature$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^humidity$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^pressure$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^battery$/i })).toBeInTheDocument();
  });

  it("keeps a per-plot export button but no configuration controls", () => {
    render(<HistoricalCharts data={data} />);

    expect(screen.getAllByRole("button", { name: /export chart image/i })).toHaveLength(4);
    expect(screen.queryByRole("button", { name: /add chart/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/chart settings/i)).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no numeric metrics", () => {
    render(<HistoricalCharts data={[]} />);

    expect(screen.getByText(/no data available/i)).toBeInTheDocument();
    expect(screen.queryAllByTestId("chart-line")).toHaveLength(0);
  });
});
