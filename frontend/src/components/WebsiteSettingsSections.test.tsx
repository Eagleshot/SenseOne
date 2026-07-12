import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Accordion } from "@/components/ui/accordion";
import { DangerZoneSection } from "@/components/WebsiteSettingsSections";

const mockRotateSecret = vi.fn();

const renderSection = () =>
  render(
    <Accordion type="multiple" defaultValue={["danger-zone"]}>
      <DangerZoneSection
        stationId="abc123def456"
        stationName="Ridge Cam"
        isDeleteDialogOpen={false}
        setDeleteDialogOpen={() => {}}
        isDeleting={false}
        deleteError={null}
        handleConfirmDelete={() => {}}
        onRotateSecret={mockRotateSecret}
      />
    </Accordion>
  );

describe("DangerZoneSection secret rotation", () => {
  beforeEach(() => {
    mockRotateSecret.mockReset();
  });

  it("rotates after confirmation and shows the one-time secret with the station id", async () => {
    mockRotateSecret.mockResolvedValue({ success: true, secret: "fresh-secret-b64" });

    renderSection();
    fireEvent.click(screen.getByRole("button", { name: /rotate secret/i }));
    const confirmButton = await screen.findByRole("button", { name: /rotate now/i });
    expect(mockRotateSecret).not.toHaveBeenCalled(); // not before the explicit confirm

    fireEvent.click(confirmButton);

    expect(await screen.findByDisplayValue("fresh-secret-b64")).toBeInTheDocument();
    expect(screen.getByDisplayValue("abc123def456")).toBeInTheDocument();
    expect(screen.getByText(/only once/i)).toBeInTheDocument();
    expect(mockRotateSecret).toHaveBeenCalledTimes(1);
  });

  it("shows the error and keeps the confirm screen when rotation fails", async () => {
    mockRotateSecret.mockResolvedValue({ success: false, error: "Unable to provision a device secret." });

    renderSection();
    fireEvent.click(screen.getByRole("button", { name: /rotate secret/i }));
    fireEvent.click(screen.getByRole("button", { name: /rotate now/i }));

    expect(await screen.findByText(/unable to provision/i)).toBeInTheDocument();
    // Still on the confirm screen — the user can retry.
    expect(screen.getByRole("button", { name: /rotate now/i })).toBeInTheDocument();
  });
});
