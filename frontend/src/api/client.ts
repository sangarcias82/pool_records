/** Fetch wrapper: same-origin JSON with the session cookie. */

/**
 * ``key`` is the server's i18n key (its ``message`` is already translated by the server), or a SPA key for errors
 * produced here (``local``): ``err.network`` (server unreachable) and ``err.http`` (error without a JSON body).
 */
export class ApiError extends Error {
  constructor(public status: number, message: string, public key?: string, public local = false) {
    super(message);
  }
}

type Translate = (key: string, params?: Record<string, string | number>) => string;

let unauthorizedHandler: (() => void) | null = null;

/** The auth context registers here so any 401 sends the user back to the login screen. */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: "include",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Network error", "err.network", true); // offline, server stopped, DNS...
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/login")) unauthorizedHandler?.();
    if (typeof payload?.detail !== "string") throw new ApiError(response.status, `HTTP ${response.status}`, "err.http", true);
    throw new ApiError(response.status, payload.detail, payload.key);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};

/** Text to show for an error: server messages as sent (already translated), SPA-side errors through ``t``. */
export function errorMessage(error: unknown, t?: Translate): string {
  if (error instanceof ApiError && error.local && error.key && t) return t(error.key, { status: error.status });
  return error instanceof Error ? error.message : String(error);
}
