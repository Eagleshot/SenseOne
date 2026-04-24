import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RawDataTable } from "@/components/RawDataTable";
import { TEMPERATURE_UNIT } from "@/lib/units";

const mockUseApp = vi.fn();

vi.mock("@/contexts/useApp", () => ({
  useApp: () => mockUseApp(),
}));

const duplicateTimestampRows = [
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
  {
    timestamp: new Date("2026-01-02T10:00:00Z"),
    temperature: 21,
    humidity: 47,
    pressure: 1011,
    battery: 84,
    windSpeed: 12,
    windDirection: 170,
    visibility: 7,
    uvIndex: 1,
    dewPoint: 11,
    feelsLike: 20,
  },
];

const readBlobAsText = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });

describe("RawDataTable", () => {
  beforeEach(() => {
    mockUseApp.mockReset();
    mockUseApp.mockReturnValue({
      timezone: "UTC",
    });
  });

  it("renders duplicate timestamps as distinct rows and exports the shared temperature unit", async () => {
    let capturedBlob: Blob | undefined;

    Object.assign(URL, {
      createObjectURL: vi.fn((blob: Blob) => {
        capturedBlob = blob;
        return "blob:mock";
      }),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<RawDataTable data={duplicateTimestampRows} />);

    fireEvent.click(screen.getByRole("button", { name: /expand raw data/i }));

    expect(screen.getAllByText(`21 ${TEMPERATURE_UNIT}`)).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: /download csv/i }));

    expect(capturedBlob).toBeDefined();
    await expect(readBlobAsText(capturedBlob!)).resolves.toContain(`Temperature (${TEMPERATURE_UNIT})`);
  });
});
