import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiError } from "./client";

describe("apiClient", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the backend via a relative path, with no hardcoded host", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(new Response("{}", { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.get("/health");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/health");
  });

  it("throws a distinct network.unreachable ApiError when fetch itself fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );

    await expect(apiClient.get("/health")).rejects.toMatchObject({
      messageKey: "network.unreachable",
      status: 0,
    });
    await expect(apiClient.get("/health")).rejects.toBeInstanceOf(ApiError);
  });

  it("throws an ApiError carrying the backend's message_key for a real error response", async () => {
    // Distinguish by URL, the way LoginPage.test.tsx does: a 401 from
    // /auth/login must not be swallowed by the refresh-and-retry path that
    // only applies to *other* endpoints' expired-access-token 401s.
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/auth/refresh")) {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: { message_key: "auth.missing_token" } }), {
              status: 401,
            }),
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify({ detail: { message_key: "auth.invalid_credentials" } }), {
            status: 401,
          }),
        );
      }),
    );

    await expect(apiClient.post("/auth/login", { email: "a@b.com", password: "x" })).rejects.toMatchObject({
      messageKey: "auth.invalid_credentials",
      status: 401,
    });
  });
});
