import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CreateStationDialog } from "@/components/CreateStationDialog";

const mockCreateStation = vi.fn();
const mockRotateDeviceSecret = vi.fn();
const mockReverseGeocode = vi.fn();

vi.mock("@/contexts/AppContext", () => ({
  useStationData: () => ({
    createStation: mockCreateStation,
    rotateDeviceSecret: mockRotateDeviceSecret,
  }),
}));

vi.mock("@/api/geo", () => ({
  reverseGeocode: (...args: unknown[]) => mockReverseGeocode(...args),
}));

// Leaflet doesn't render in jsdom; stand in with a button that picks a point.
vi.mock("@/components/CoordinatePicker", () => ({
  CoordinatePicker: ({ onChange }: { onChange: (lat: number, lon: number) => void }) => (
    <button type="button" onClick={() => onChange(47.376, 8.541)}>
      pick-on-map
    </button>
  ),
}));

const openDialog = () => {
  render(<CreateStationDialog trigger={<button type="button">New station</button>} />);
  fireEvent.click(screen.getByRole("button", { name: /new station/i }));
};

describe("CreateStationDialog", () => {
  beforeEach(() => {
    mockCreateStation.mockReset();
    mockRotateDeviceSecret.mockReset();
    mockReverseGeocode.mockReset();
    mockReverseGeocode.mockResolvedValue(null); // prefill is best-effort by default
  });

  it("validates name and coordinates before submitting", async () => {
    openDialog();
    fireEvent.click(screen.getByRole("button", { name: /create station/i }));

    expect(await screen.findByText(/station name is required/i)).toBeInTheDocument();
    expect(mockCreateStation).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Ridge Cam" } });
    fireEvent.click(screen.getByRole("button", { name: /create station/i }));
    expect(await screen.findByText(/pick the station location/i)).toBeInTheDocument();
    expect(mockCreateStation).not.toHaveBeenCalled();
  });

  it("creates the station and shows the one-time provisioning values", async () => {
    mockCreateStation.mockResolvedValue({ success: true, stationId: "abc123def456" });
    mockRotateDeviceSecret.mockResolvedValue({ success: true, secret: "top-secret-b64" });

    openDialog();
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Ridge Cam" } });
    fireEvent.click(screen.getByRole("button", { name: /pick-on-map/i }));
    fireEvent.click(screen.getByRole("button", { name: /create station/i }));

    // Success screen: both firmware values are shown, with the one-time warning.
    expect(await screen.findByDisplayValue("abc123def456")).toBeInTheDocument();
    expect(await screen.findByDisplayValue("top-secret-b64")).toBeInTheDocument();
    expect(screen.getByText(/only once/i)).toBeInTheDocument();
    // Public is the default visibility.
    expect(mockCreateStation).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Ridge Cam", lat: 47.376, lon: 8.541, isPublic: true })
    );
  });

  it("creates a private station when the private tile is selected", async () => {
    mockCreateStation.mockResolvedValue({ success: true, stationId: "abc123def456" });
    mockRotateDeviceSecret.mockResolvedValue({ success: true, secret: "top-secret-b64" });

    openDialog();
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Ridge Cam" } });
    fireEvent.click(screen.getByRole("button", { name: /pick-on-map/i }));
    fireEvent.click(screen.getByRole("button", { name: /private/i }));
    fireEvent.click(screen.getByRole("button", { name: /create station/i }));

    await screen.findByDisplayValue("abc123def456");
    expect(mockCreateStation).toHaveBeenCalledWith(expect.objectContaining({ isPublic: false }));
  });

  it("offers a retry when secret provisioning fails", async () => {
    mockCreateStation.mockResolvedValue({ success: true, stationId: "abc123def456" });
    mockRotateDeviceSecret
      .mockResolvedValueOnce({ success: false, error: "Unable to provision a device secret." })
      .mockResolvedValueOnce({ success: true, secret: "second-try-secret" });

    openDialog();
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Ridge Cam" } });
    fireEvent.click(screen.getByRole("button", { name: /pick-on-map/i }));
    fireEvent.click(screen.getByRole("button", { name: /create station/i }));

    expect(await screen.findByText(/unable to provision/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByDisplayValue("second-try-secret")).toBeInTheDocument();
    expect(mockRotateDeviceSecret).toHaveBeenCalledTimes(2);
  });

  it("prefills location and country from the picked map point", async () => {
    mockReverseGeocode.mockResolvedValue({ name: "Davos", countryCode: "CH", state: "Grisons" });

    openDialog();
    fireEvent.click(screen.getByRole("button", { name: /pick-on-map/i }));

    await waitFor(() => expect(screen.getByLabelText(/location/i)).toHaveValue("Davos"));
    expect(screen.getByRole("combobox")).toHaveTextContent("Switzerland");
    expect(mockReverseGeocode).toHaveBeenCalledWith(47.376, 8.541, expect.any(AbortSignal));
  });

  it("never overwrites a user-typed location with the geocoded one", async () => {
    mockReverseGeocode.mockResolvedValue({ name: "Davos", countryCode: "CH", state: null });

    openDialog();
    fireEvent.change(screen.getByLabelText(/location/i), { target: { value: "My Backyard" } });
    fireEvent.click(screen.getByRole("button", { name: /pick-on-map/i }));

    // Country (untouched) fills; the typed location stays.
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveTextContent("Switzerland"));
    expect(screen.getByLabelText(/location/i)).toHaveValue("My Backyard");
  });

  it("shows the create error and stays on the form when creation fails", async () => {
    mockCreateStation.mockResolvedValue({ success: false, error: "Unable to create station." });

    openDialog();
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Ridge Cam" } });
    fireEvent.click(screen.getByRole("button", { name: /pick-on-map/i }));
    fireEvent.click(screen.getByRole("button", { name: /create station/i }));

    expect(await screen.findByText(/unable to create station/i)).toBeInTheDocument();
    // Still on the form; no provisioning was attempted.
    await waitFor(() => expect(screen.getByLabelText(/name/i)).toBeInTheDocument());
    expect(mockRotateDeviceSecret).not.toHaveBeenCalled();
  });
});
