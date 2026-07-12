import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QuickInfoCards } from "@/components/QuickInfoCards";

const mockUseStationData = vi.fn();

vi.mock("@/contexts/AppContext", () => ({
  useStationData: () => mockUseStationData(),
}));

describe("QuickInfoCards", () => {
  beforeEach(() => {
    mockUseStationData.mockReset();
  });

  it("shows the backend battery value immediately when available", () => {
    mockUseStationData.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: 82, isOnline: true },
      historicalData: [],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("Battery")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
  });

  it("falls back to the latest history battery when backend battery is unavailable", () => {
    mockUseStationData.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: null, isOnline: true },
      historicalData: [{ timestamp: new Date(), battery: 61 }],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("61%")).toBeInTheDocument();
  });

  it("shows reception from the latest reading when the device reports it", () => {
    mockUseStationData.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: null, isOnline: true },
      historicalData: [{ timestamp: new Date(), battery: 55, reception: 88 }],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("Reception")).toBeInTheDocument();
    expect(screen.getByText("88%")).toBeInTheDocument();
  });

  it("renders nothing when no status metrics are available", () => {
    mockUseStationData.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: null, isOnline: true },
      historicalData: [],
    });

    const { container } = render(<QuickInfoCards />);

    expect(container.firstChild).toBeNull();
  });
});
