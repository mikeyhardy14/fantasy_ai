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
    vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
      if (String(url).includes("/standings")) return jsonResponse([]);
      return fetchMock(url, init);
    });
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
    vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
      if (String(url).includes("/standings")) return jsonResponse([]);
      return fetchMock(url, init);
    });
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

  it("asks before adding and dropping, and writes only after approval", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    window.localStorage.setItem("omaha.lineup-auto-approve", "1");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        message: "Add Free Agent and drop Bench Receiver. Approve it in the chat.",
        tools_used: ["claim_player"],
        generated_by: "deterministic",
        suggested_questions: [],
        actions: [],
        claims: [{
          summary: "Add Free Agent and drop Bench Receiver.",
          add_player_id: "free-1",
          add_player_name: "Free Agent",
          add_position: "RB",
          add_headshot_url: null,
          drop_player_id: "bench-1",
          drop_player_name: "Bench Receiver",
          drop_position: "WR",
          detail: "RB · 9.4 proj · drop Bench Receiver (bench)",
        }],
      }))
      .mockResolvedValueOnce(jsonResponse({
        team: {},
        verified: true,
        public_api_confirmed: false,
        message: "Dropped Bench Receiver. Free Agent is on your bench.",
      }));
    vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
      if (String(url).includes("/standings")) return jsonResponse([]);
      return fetchMock(url, init);
    });
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Chat leagueId="league-1" aiEnabled />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText("Message"), "add Free Agent and drop Bench Receiver");
    await user.click(screen.getByRole("button", { name: "Send" }));
    const approval = await screen.findByTestId("roster-approval");
    expect(approval).toHaveTextContent("Add Free Agent and drop Bench Receiver.");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("claim-approve"));
    expect(await screen.findByTestId("claim-result")).toHaveTextContent("Dropped Bench Receiver. Free Agent is on your bench.");
    const move = fetchMock.mock.calls[1];
    expect(String(move[0])).toContain("/api/leagues/league-1/roster/add");
    expect(JSON.parse(String(move[1].body))).toEqual({ player_id: "free-1", drop_player_id: "bench-1" });
  });

  it("mentions another team with @ and sends that team's id", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/standings")) {
        return jsonResponse([
          { id: "mine", name: "Mike's Marauders", owner_name: "Mike", record: "2-1", is_user_team: true },
          { id: "team-4", name: "Touchdown Titans", owner_name: "Sam", record: "4-2", is_user_team: false },
        ]);
      }
      return jsonResponse({
        message: "They start Rex.",
        tools_used: ["get_team_roster"],
        generated_by: "deterministic",
        suggested_questions: [],
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Chat leagueId="league-1" aiEnabled />
      </QueryClientProvider>,
    );

    const box = screen.getByLabelText("Message");
    await user.type(box, "@Tou");
    const option = await screen.findByRole("option", { name: /Touchdown Titans/ });
    expect(screen.queryByRole("option", { name: /Mike's Marauders/ })).not.toBeInTheDocument();
    await user.click(option);
    expect(box).toHaveValue("@Touchdown Titans ");
    await user.type(box, "who should I target?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("They start Rex.")).toBeInTheDocument();
    expect(screen.getByTestId("msg-user")).toHaveTextContent("@Touchdown Titans who should I target?");
    expect(screen.getByTestId("msg-user")).not.toHaveTextContent("team_id");
    const chatCall = fetchMock.mock.calls.find((call) => String(call[0]).includes("/ai/chat"));
    const body = JSON.parse(String(chatCall?.[1]?.body));
    expect(body.messages[0].content).toBe("@Touchdown Titans (team_id team-4) who should I target?");
  });
});
