import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StationSummaryResponse, TimelineItemResponse } from "@/api/stations";
import { NOT_FOUND_LABEL } from "@/lib/placeholders";

import { useWebcamData } from "./useWebcamData";

const API_BASE = "/api";

const STATIONS: StationSummaryResponse[] = [
  {
    id: "aaa111",
    urlSlug: "alpha-cam",
    name: "Alpha Cam",
    location: "Alpha Ridge",
    coordinates: { lat: 47, lng: 8, altitude: 1000 },
    isPublic: true,
    isOnline: true,
  } as StationSummaryResponse,
  {
    id: "bbb222",
    urlSlug: "beta-cam",
    name: "Beta Cam",
    location: "Beta Valley",
    coordinates: { lat: 46, lng: 7, altitude: 500 },
    isPublic: true,
    isOnline: false,
  } as StationSummaryResponse,
];

// Mutable per-test fixtures. Tests mutate these between refetches:
// image timelines per station id (oldest-to-newest, like the API), and whether
// the "caller" is signed in (the detail endpoint reports canEdit accordingly,
// like the backend does for an owner).
let timelines: Record<string, TimelineItemResponse[]>;
let authenticated: boolean;

const timelineItem = (stationId: string, n: number): TimelineItemResponse => ({
  timestamp: `2026-06-11T0${n}:00:00Z`,
  url: `/stations/${stationId}/images/${n}.jpg`,
});

const jsonOk = (body: unknown) =>
  Promise.resolve(
    new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })
  );

const installFetchMock = () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }));
      if (new RegExp(`${API_BASE}/stations(\\?.*)?$`).test(url)) return jsonOk(STATIONS);
      const match = url.match(new RegExp(`${API_BASE}/stations/([^/?]+)(?:/([a-z-]+))?`));
      if (!match) return jsonOk(null);
      const stationId = decodeURIComponent(match[1]);
      const resource = match[2];
      if (!resource) {
        const station = STATIONS.find((item) => item.id === stationId);
        return station
          ? jsonOk({ ...station, canEdit: authenticated })
          : Promise.resolve(new Response(JSON.stringify({ detail: "Unknown station id." }), { status: 404 }));
      }
      if (resource === "data" || resource === "readings") return jsonOk([]);
      if (resource === "image-captures") return jsonOk(timelines[stationId] ?? []);
      return jsonOk(null);
    })
  );
};

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const renderWebcamData = () =>
  renderHook(({ isAuthenticated }) => useWebcamData(API_BASE, isAuthenticated, true), {
    wrapper: createWrapper(),
    initialProps: { isAuthenticated: false },
  });

describe("useWebcamData", () => {
  beforeEach(() => {
    timelines = { aaa111: [timelineItem("aaa111", 1), timelineItem("aaa111", 2), timelineItem("aaa111", 3)] };
    authenticated = false;
    installFetchMock();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it("defaults to the first station when the URL has no token", async () => {
    const { result } = renderWebcamData();
    // While resolving, the loading flag drives skeletons instead of "Loading..." text.
    expect(result.current.station.isStationLoading).toBe(true);
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("aaa111"));
    await waitFor(() => expect(result.current.station.isStationLoading).toBe(false));
  });

  it("resolves a url slug in the address bar to its station", async () => {
    window.history.replaceState(null, "", "/stations/beta-cam");
    const { result } = renderWebcamData();
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("bbb222"));
  });

  it("shows the not-found state for an unknown token instead of another station", async () => {
    window.history.replaceState(null, "", "/stations/ghost-cam");
    const { result } = renderWebcamData();
    await waitFor(() => expect(result.current.station.activeWebcam.name).toBe(NOT_FOUND_LABEL));
    // The token is kept so the same URL can resolve after a sign-in.
    expect(result.current.station.activeWebcam.id).toBe("ghost-cam");
  });

  it("refetches station detail after login so canEdit appears without a refresh", async () => {
    window.history.replaceState(null, "", "/stations/alpha-cam");
    const { result, rerender } = renderWebcamData();
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("aaa111"));
    expect(result.current.station.canEdit).toBe(false);

    // Sign in: the detail must be refetched (auth is part of the query key),
    // not served stale from the anonymous cache entry.
    authenticated = true;
    rerender({ isAuthenticated: true });
    await waitFor(() => expect(result.current.station.canEdit).toBe(true));
  });

  it("refetches history with the requested lookback window", async () => {
    window.history.replaceState(null, "", "/stations/alpha-cam");
    const { result } = renderWebcamData();
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("aaa111"));

    const fetchMock = window.fetch as ReturnType<typeof vi.fn>;
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/data?hours=24"))).toBe(true)
    );

    act(() => result.current.station.setHistoryWindowHours(72));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/data?hours=72"))).toBe(true)
    );

    // Absolute ranges are not capped by the one-year relative preset.
    act(() => result.current.station.setHistoryWindowHours(10_000));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/data?hours=10000"))).toBe(true)
    );
  });

  it("moves the selection to the next station after deleting the active one", async () => {
    window.history.replaceState(null, "", "/stations/alpha-cam");
    authenticated = true;
    const { result, rerender } = renderWebcamData();
    rerender({ isAuthenticated: true });
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("aaa111"));

    let deleteResult: { success: boolean; error?: string } | undefined;
    await act(async () => {
      deleteResult = await result.current.station.deleteStation("aaa111");
    });

    expect(deleteResult).toEqual({ success: true });
    expect(result.current.station.activeWebcam.id).toBe("bbb222");
    expect(result.current.station.webcamList.map((webcam) => webcam.id)).toEqual(["bbb222"]);
    expect(window.location.pathname).toBe("/stations/beta-cam");
  });

  it("follows browser back/forward (popstate) to the station in the URL", async () => {
    window.history.replaceState(null, "", "/stations/alpha-cam");
    const { result } = renderWebcamData();
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("aaa111"));

    act(() => {
      window.history.replaceState(null, "", "/stations/beta-cam");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await waitFor(() => expect(result.current.station.activeWebcam.id).toBe("bbb222"));
  });

  it("jumps to the newest image on load, but keeps a scrubbed position across refreshes", async () => {
    window.history.replaceState(null, "", "/stations/alpha-cam");
    const { result } = renderWebcamData();

    // Initial load lands on the newest of the 3 images.
    await waitFor(() => expect(result.current.station.imageTimeline).toHaveLength(3));
    await waitFor(() => expect(result.current.playback.currentImageIndex).toBe(2));

    // Scrub back to the oldest image, then a refresh delivers a 4th capture.
    act(() => result.current.playback.setCurrentImageIndex(0));
    timelines.aaa111 = [...timelines.aaa111, timelineItem("aaa111", 4)];
    await act(async () => {
      await result.current.station.refreshImageTimeline();
    });
    await waitFor(() => expect(result.current.station.imageTimeline).toHaveLength(4));
    // Still on the image the viewer scrubbed to, not yanked to the new head.
    expect(result.current.playback.currentImageIndex).toBe(0);

    // From the newest image, a refresh follows the new head.
    act(() => result.current.playback.setCurrentImageIndex(3));
    timelines.aaa111 = [...timelines.aaa111, timelineItem("aaa111", 5)];
    await act(async () => {
      await result.current.station.refreshImageTimeline();
    });
    await waitFor(() => expect(result.current.playback.currentImageIndex).toBe(4));
  });
});
