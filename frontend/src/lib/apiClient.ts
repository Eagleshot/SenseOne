export const apiBaseUrl: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

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

export type PostJsonResult<T> = { ok: true; data: T } | { ok: false; error: string };

type PostJsonOptions = {
  /** JSON-serialized into the body (and sets Content-Type) when present; omit for an empty POST. */
  body?: unknown;
  /** Per-status error message used when the response carries no usable `detail`. */
  errorFallback: (status: number) => string;
  /** Message returned when the request never reaches the server (or the success body isn't JSON). */
  networkError: string;
};

/**
 * POST helper for mutating endpoints that need a per-status error message.
 * Centralizes the fetch / `!ok` -> status-fallback + `extractErrorDetail` / network-catch
 * scaffold; callers map `data` to their own success shape.
 */
export const postJson = async <T,>(
  url: string,
  { body, errorFallback, networkError }: PostJsonOptions,
): Promise<PostJsonResult<T>> => {
  try {
    const response = await fetch(url, {
      method: "POST",
      credentials: "include",
      ...(body !== undefined
        ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
        : {}),
    });

    if (!response.ok) {
      const fallback = errorFallback(response.status);
      let message = fallback;
      try {
        message = extractErrorDetail(await response.json(), fallback);
      } catch {
        // Keep the status fallback when the error body is empty or invalid JSON.
      }
      return { ok: false, error: message };
    }

    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, error: networkError };
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

