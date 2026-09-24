import { api, ApiError, tokenStore } from "@/lib/api";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("api client", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("attaches the bearer token and parses JSON", async () => {
    tokenStore.set("abc");
    const fetchMock = mockFetch(200, [{ id: "1", name: "League" }]);
    const leagues = await api.leagues.list();
    expect(leagues[0].name).toBe("League");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/leagues$/);
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer abc");
  });

  it("throws ApiError with the backend message", async () => {
    mockFetch(404, { error: { code: "provider_not_found", message: "No Sleeper user named 'ghost' was found.", details: { provider: "sleeper" } } });
    await expect(api.integrations.connectSleeper("ghost")).rejects.toMatchObject({
      status: 404,
      code: "provider_not_found",
      message: "No Sleeper user named 'ghost' was found.",
    });
  });

  it("clears the token and emits an event on 401", async () => {
    tokenStore.set("expired");
    const listener = vi.fn();
    window.addEventListener("fantasy-ai:unauthorized", listener);
    mockFetch(401, { error: { code: "unauthorized", message: "Session expired." } });
    await expect(api.auth.me()).rejects.toBeInstanceOf(ApiError);
    expect(tokenStore.get()).toBeNull();
    expect(listener).toHaveBeenCalled();
  });

  it("does not sign the user out when a provider token is rejected", async () => {
    tokenStore.set("session");
    mockFetch(401, { error: { code: "provider_auth_error", message: "Sleeper rejected the token." } });
    await expect(api.auth.me()).rejects.toBeInstanceOf(ApiError);
    expect(tokenStore.get()).toBe("session");
  });

  it("wraps network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.health()).rejects.toMatchObject({ code: "network_error" });
  });

  it("serialises query params and skips empty ones", async () => {
    const fetchMock = mockFetch(200, []);
    await api.leagues.players("L1", { position: "RB", search: undefined, available: true, limit: 10 });
    expect(fetchMock.mock.calls[0][0]).toBe(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/leagues/L1/players?position=RB&available=true&limit=10`);
  });
});
