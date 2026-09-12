// Relative by default - resolves against whatever origin served the page
// (localhost, or a phone's LAN IP), so it works unmodified from any device.
// vite.config.ts proxies /api to the backend in dev; a production build only
// needs VITE_API_BASE_URL set if the frontend and backend are ever deployed
// to different origins (see .env.example).
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public messageKey: string,
    public params: Record<string, unknown> = {},
  ) {
    super(messageKey);
  }
}

async function request<T>(path: string, options: RequestInit = {}, allowRefresh = true): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    // fetch() itself threw: DNS failure, connection refused, offline, etc. -
    // never surfaced as a raw TypeError, always as a distinct, translatable
    // "can't reach the server" ApiError so the UI can tell this apart from a
    // 401/403/422 response the server actually sent.
    throw new ApiError(0, "network.unreachable");
  }

  if (response.status === 401 && allowRefresh && path !== "/auth/refresh") {
    try {
      const refreshed = await request<{ access_token: string }>(
        "/auth/refresh",
        { method: "POST" },
        false,
      );
      accessToken = refreshed.access_token;
      return request<T>(path, options, false);
    } catch {
      // Refresh failed - fall through and surface the original 401 below.
    }
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: { message_key?: string; params?: Record<string, unknown> } }
      | null;
    const detail = body?.detail ?? {};
    throw new ApiError(response.status, detail.message_key ?? "error.unknown", detail.params ?? {});
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
