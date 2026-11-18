/** Fetch wrapper: same-origin JSON with the session cookie. */

export class ApiError extends Error {
  constructor(public status: number, message: string, public key?: string) {
    super(message);
  }
}

let unauthorizedHandler: (() => void) | null = null;

/** The auth context registers here so any 401 sends the user back to the login screen. */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/login")) unauthorizedHandler?.();
    throw new ApiError(response.status, payload?.detail || response.statusText, payload?.key);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown = {}) => request<T>("POST", path, body),
};

export const errorMessage = (error: unknown): string => (error instanceof Error ? error.message : String(error));
