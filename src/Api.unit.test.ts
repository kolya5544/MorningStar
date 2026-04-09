import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("Api auth flow", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("refreshes tokens after 401 and retries the original request", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: "new-access",
            refresh_token: "new-refresh",
            token_type: "bearer",
            expires_in: 111,
            refresh_expires_in: 222,
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [],
            page: 1,
            page_size: 6,
            total_items: 0,
            total_pages: 1,
          }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        ),
      );

    const api = await import("@/Api");
    api.setAuthTokens({ accessToken: "old-access", refreshToken: "old-refresh" });

    const result = await api.listPortfolios();

    expect(result.total_items).toBe(0);
    expect(localStorage.getItem("ms_access_token")).toBe("new-access");
    expect(localStorage.getItem("ms_refresh_token")).toBe("new-refresh");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/auth/refresh",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/portfolios",
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );
  });

  it("clears tokens when refresh fails", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "expired" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "refresh expired" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      );

    const api = await import("@/Api");
    api.setAuthTokens({ accessToken: "old-access", refreshToken: "old-refresh" });

    await expect(api.listPortfolios()).rejects.toMatchObject({ status: 401 });
    expect(localStorage.getItem("ms_access_token")).toBeNull();
    expect(localStorage.getItem("ms_refresh_token")).toBeNull();
  });
});
