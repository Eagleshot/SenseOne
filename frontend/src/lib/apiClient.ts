export const apiBaseUrl: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

type FetchJsonOptions = RequestInit & {
  throwOnHttpError?: boolean;
};

export const isAbortError = (error: unknown): boolean =>
  error instanceof DOMException && error.name === "AbortError";

/**
 * Fetch JSON from the backend.
 * - Returns `null` on HTTP errors when `throwOnHttpError` is false.
 * - Returns `null` on empty/non-JSON success bodies (instead of throwing,
 *   which would otherwise leak past callers that branch on null).
 */
export const fetchJson = async <T,>(
  url: string,
  options: FetchJsonOptions = {},
): Promise<T | null> => {
  const { throwOnHttpError = true, ...requestInit } = options;
  const response = await fetch(url, requestInit);

  if (!response.ok) {
    if (throwOnHttpError) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return null;
  }

  try {
    const text = await response.text();
    if (!text) return null;
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
};

/**
 * FastAPI returns `detail` as either a string or a list of validation
 * errors. Normalize to a single string for display.
 */
export const extractErrorDetail = (
  payload: unknown,
  fallback: string,
): string => {
  if (!payload || typeof payload !== "object") return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string"
          ? (item as { msg: string }).msg
          : null,
      )
      .filter((value): value is string => Boolean(value));
    if (messages.length > 0) return messages.join("; ");
  }
  return fallback;
};

export const stationUrl = (stationId: string, suffix = ""): string =>
  `${apiBaseUrl}/stations/${encodeURIComponent(stationId)}${suffix}`;
