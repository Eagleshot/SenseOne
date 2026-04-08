import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QuickInfoCards } from "@/components/QuickInfoCards";

const mockUseApp = vi.fn();

vi.mock("@/contexts/useApp", () => ({
  useApp: () => mockUseApp(),
}));

describe("QuickInfoCards", () => {
  beforeEach(() => {
    mockUseApp.mockReset();
  });

  it("shows the backend battery value immediately when available", () => {
    mockUseApp.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: 82, isOnline: true },
      historicalData: [],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("82%")).toBeInTheDocument();
  });

  it("falls back to the latest history battery when backend battery is unavailable", () => {
    mockUseApp.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: null, isOnline: true },
      historicalData: [
        { battery: 61 },
      ],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("61%")).toBeInTheDocument();
  });

  it("shows unavailable when the backend resolved without battery data", () => {
    mockUseApp.mockReturnValue({
      activeWebcam: { id: "cam-1", battery: null, isOnline: true },
      historicalData: [],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("shows loading while station battery data is still unresolved", () => {
    mockUseApp.mockReturnValue({
      activeWebcam: { id: "cam-1", isOnline: true },
      historicalData: [],
    });

    render(<QuickInfoCards />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
