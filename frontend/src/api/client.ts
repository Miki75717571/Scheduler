const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000/api/v1";

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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  });

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
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};
