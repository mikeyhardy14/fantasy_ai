import ConnectSleeperPage from "@/app/(app)/connect/sleeper/page";
import type { FantasyAccount, League, ProviderLeague } from "@/lib/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const push = vi.fn();
const select = vi.fn();
const refetch = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/connect/sleeper",
  redirect: vi.fn(),
}));

vi.mock("@/lib/league", () => ({
  useLeague: () => ({
    leagues: [],
    loading: false,
    error: null,
    selected: null,
    select,
    refetch,
  }),
}));

const account: FantasyAccount = {
  id: "acc-1",
  provider: "sleeper",
  external_user_id: "111",
  username: "mikefantasy",
  display_name: "MikeFantasy",
  avatar: null,
  created_at: "2026-09-01T00:00:00Z",
  last_synced_at: null,
  writes_enabled: false,
};

function providerLeague(overrides: Partial<ProviderLeague> = {}): ProviderLeague {
  return {
    external_league_id: "1",
    name: "Dynasty",
    season: 2026,
    team_count: 12,
    status: "in_season",
    avatar: null,
    scoring_type: "PPR",
    imported: false,
    ...overrides,
  };
}

function importedLeague(overrides: Partial<League> = {}): League {
  return {
    id: "league-1",
    provider: "sleeper",
    external_league_id: "1",
    name: "Dynasty",
    season: 2026,
    team_count: 12,
    current_week: 5,
    status: "in_season",
    avatar: null,
    scoring_type: "PPR",
    last_synced_at: null,
    sync_status: "success",
    sync_error: null,
    user_team_id: "team-1",
    user_team_name: "Mike's Marauders",
    ...overrides,
  };
}

function json(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConnectSleeperPage />
    </QueryClientProvider>,
  );
}

describe("Connect Sleeper import all", () => {
  beforeEach(() => {
    window.localStorage.clear();
    push.mockReset();
    select.mockReset();
    refetch.mockReset();
  });

  it("imports every pending league and opens Multi-Box", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
      const path = String(url);
      if (path.endsWith("/api/integrations/accounts")) return json([account]);
      if (path.includes("/leagues/import-all")) {
        return json([importedLeague(), importedLeague({ id: "league-2", external_league_id: "2", name: "Redraft" })]);
      }
      if (path.includes("/api/integrations/sleeper/leagues")) {
        return json({
          account,
          season: 2026,
          leagues: [providerLeague(), providerLeague({ external_league_id: "2", name: "Redraft" })],
        });
      }
      return json({ error: { code: "not_found", message: path } }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("button", { name: "Import all (2)" })).toBeInTheDocument();
    expect(screen.getAllByTestId("provider-league")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "Import all (2)" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/leagues/import-all") && (init as RequestInit | undefined)?.method === "POST");
      expect(call).toBeTruthy();
    });
    await waitFor(() => expect(select).toHaveBeenCalledWith("league-1"));
    expect(push).toHaveBeenCalledWith("/multibox");
    expect(refetch).toHaveBeenCalled();
  });

  it("imports remaining leagues when some are already live", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const path = String(url);
        if (path.endsWith("/api/integrations/accounts")) return json([account]);
        if (path.includes("/leagues/import-all")) return json([importedLeague({ id: "league-2", external_league_id: "2", name: "Redraft" })]);
        if (path.includes("/api/integrations/sleeper/leagues")) {
          return json({
            account,
            season: 2026,
            leagues: [
              providerLeague({ imported: true }),
              providerLeague({ external_league_id: "2", name: "Redraft" }),
            ],
          });
        }
        return json({ error: { code: "not_found", message: path } }, 404);
      }),
    );

    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("button", { name: "Import remaining (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import remaining (1)" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
  });

  it("hides import-all when every league is already live", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const path = String(url);
        if (path.endsWith("/api/integrations/accounts")) return json([account]);
        if (path.includes("/api/integrations/sleeper/leagues")) {
          return json({
            account,
            season: 2026,
            leagues: [providerLeague({ imported: true }), providerLeague({ external_league_id: "2", name: "Redraft", imported: true })],
          });
        }
        return json({ error: { code: "not_found", message: path } }, 404);
      }),
    );

    renderPage();
    expect(await screen.findByText("Dynasty")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import all/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import remaining/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("Live")).toHaveLength(2);
  });
});
