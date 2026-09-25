import { Chat } from "@/components/chat";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

describe("Chat subs", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows the start-over summary and writes the lineup after approval", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        message: "Lamar Jackson is starting at QB. Choose who takes that spot.",
        tools_used: ["get_roster"],
        generated_by: "deterministic",
        suggested_questions: [],
        actions: [{
          label: "Sub in Cooper Rush",
          player_id: "backup-1",
          player_name: "Cooper Rush",
          position: "QB",
          headshot_url: null,
          destination: "starter",
          slot_index: 0,
          slot: "QB",
          week: 3,
          replaces: "Lamar Jackson",
          detail: "QB · 8.1 proj",
          summary: "Start Cooper Rush over Lamar Jackson at QB. Cooper Rush 8.1 projected, Lamar Jackson 22.3 projected.",
        }],
      }))
      .mockResolvedValueOnce(jsonResponse({
        team: {},
        verified: true,
        public_api_confirmed: false,
        message: "Cooper Rush is now starting at QB.",
      }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Chat leagueId="league-1" aiEnabled />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Message"), "sub Lamar Jackson");
    await user.click(screen.getByRole("button", { name: "Send" }));
    const approval = await screen.findByTestId("lineup-approval");
    expect(approval).toHaveTextContent("Start Cooper Rush over Lamar Jackson at QB.");
    expect(approval).toHaveTextContent("Cooper Rush 8.1 projected");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByTestId("sub-result")).toHaveTextContent("Cooper Rush is now starting at QB.");
    const move = fetchMock.mock.calls[1];
    expect(String(move[0])).toContain("/api/leagues/league-1/lineup/move");
    expect(JSON.parse(String(move[1].body))).toMatchObject({
      week: 3,
      player_id: "backup-1",
      destination: "starter",
      slot_index: 0,
    });
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toMatchObject({ auto_approve: false });
  });

  it("writes a single start-over when auto-approval is on", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    window.localStorage.setItem("omaha.lineup-auto-approve", "1");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        message: "Start Cooper Rush over Lamar Jackson at QB.",
        tools_used: ["get_roster"],
        generated_by: "deterministic",
        suggested_questions: [],
        actions: [{
          label: "Sub in Cooper Rush",
          summary: "Start Cooper Rush over Lamar Jackson at QB.",
          player_id: "backup-1",
          player_name: "Cooper Rush",
          position: "QB",
          headshot_url: null,
          destination: "starter",
          slot_index: 0,
          slot: "QB",
          week: 3,
          replaces: "Lamar Jackson",
          detail: "QB · 8.1 proj",
        }],
      }))
      .mockResolvedValueOnce(jsonResponse({
        team: {},
        verified: true,
        public_api_confirmed: false,
        message: "Cooper Rush is now starting at QB.",
      }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Chat leagueId="league-1" aiEnabled />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Message"), "start Cooper Rush over Lamar Jackson");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByTestId("sub-result")).toHaveTextContent("Cooper Rush is now starting at QB.");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toMatchObject({ auto_approve: true });
    expect(String(fetchMock.mock.calls[1][0])).toContain("/lineup/move");
  });
});
