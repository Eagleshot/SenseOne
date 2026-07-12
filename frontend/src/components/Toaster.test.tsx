import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "@/components/Toaster";

const Trigger: React.FC<{ message: string; variant?: "success" | "error" }> = ({ message, variant }) => {
  const { showToast } = useToast();
  return (
    <button type="button" onClick={() => showToast(message, variant)}>
      fire
    </button>
  );
};

describe("Toaster", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a toast and dismisses it automatically", () => {
    render(
      <ToastProvider>
        <Trigger message="Schedule saved." />
      </ToastProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getByRole("status")).toHaveTextContent("Schedule saved.");

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("stacks multiple toasts independently", () => {
    render(
      <ToastProvider>
        <Trigger message="First." />
      </ToastProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "fire" }));
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireEvent.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getAllByRole("status")).toHaveLength(2);

    // The older toast expires first.
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });
});
