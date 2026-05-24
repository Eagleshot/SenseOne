const STATION_ROUTE_PREFIX = "/stations";

export const createStationPath = (stationId: string): string =>
  `${STATION_ROUTE_PREFIX}/${encodeURIComponent(stationId)}`;

export const createStationUrl = (stationId: string, origin = window.location.origin): string =>
  new URL(createStationPath(stationId), origin).toString();

export const getStationIdFromPathname = (pathname: string): string | null => {
  const match = pathname.match(/^\/stations\/([^/]+)\/?$/);
  if (!match?.[1]) return null;

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
};

export const getStationIdFromLocation = (location: Pick<Location, "pathname" | "search">): string | null => {
  const pathStationId = getStationIdFromPathname(location.pathname);
  if (pathStationId) return pathStationId;

  return new URLSearchParams(location.search).get("station")?.trim() || null;
};

export const pushStationUrl = (stationId: string) => {
  if (!stationId || typeof window === "undefined") return;

  const nextPath = createStationPath(stationId);
  if (window.location.pathname === nextPath && !window.location.search) return;

  window.history.pushState(null, "", nextPath);
};
