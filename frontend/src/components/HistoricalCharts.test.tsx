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
    XAxis: ({ domain }: { domain?: Array<number | string> }) => (
      <div data-domain={domain?.join(",")} data-testid="x-axis" />
    ),
    YAxis: () => null,
    Line: ({ dataKey }: { dataKey: string }) => <div data-key={dataKey} data-testid="chart-line" />,
    Area: () => <div data-testid="status-area" />,
  };
});

const timeRange = [new Date("2026-01-02T00:00:00Z").getTime(), new Date("2026-01-03T00:00:00Z").getTime()] as const;

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
    render(<HistoricalCharts data={data} timeRange={timeRange} />);

    expect(screen.getAllByTestId("chart-line")).toHaveLength(4);
    expect(screen.getByRole("heading", { name: /^temperature$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^humidity$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^pressure$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^battery$/i })).toBeInTheDocument();
  });

  it("renders no export or configuration controls", () => {
    render(<HistoricalCharts data={data} timeRange={timeRange} />);

    expect(screen.queryByRole("button", { name: /export chart image/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add chart/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/chart settings/i)).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no numeric metrics", () => {
    render(<HistoricalCharts data={[]} timeRange={timeRange} />);

    expect(screen.getByText(/no data available/i)).toBeInTheDocument();
    expect(screen.queryAllByTestId("chart-line")).toHaveLength(0);
  });

  it("uses the complete selected range for every plot and labels check-in status as Status", () => {
    const dataWithStatus = [{ ...data[0], nextStart: new Date("2026-01-02T11:00:00Z") }];
    render(<HistoricalCharts data={dataWithStatus} timeRange={timeRange} />);

    expect(screen.getByRole("heading", { name: "Status" })).toBeInTheDocument();
    expect(screen.getByTestId("status-area")).toBeInTheDocument();
    for (const axis of screen.getAllByTestId("x-axis")) {
      expect(axis).toHaveAttribute("data-domain", `${timeRange[0]},${timeRange[1]}`);
    }
  });
});
