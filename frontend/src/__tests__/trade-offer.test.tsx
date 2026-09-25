import { TradeOffer } from "@/components/trade-offer";
import type { Team } from "@/lib/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player, slot } from "./fixtures";

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function roster(id: string, name: string, personName: string): Team {
  return {
    team: {
      id,
      name,
      owner_name: "Owner",
      avatar: null,
      wins: 2,
      losses: 1,
      ties: 0,
      record: "2-1",
      points_for: 100,
      points_against: 90,
      faab_remaining: 40,
      waiver_position: 4,
      is_user_team: false,
    },
    week: 4,
    starters: [slot({ player: player({ id, name: personName, projected_points: 12 }) })],
    bench: [],
    reserve: [],
    lineup_slots: ["RB"],
    lineup_issues: [],
    projected_points: 12,
    projection_coverage: "full",
  };
}

describe("TradeOffer", () => {
  it("asks the assistant about that team and can analyze a picked offer", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        message: "Give Bench Receiver for their starter.",
        tools_used: ["get_team_roster"],
        generated_by: "deterministic",
        suggested_questions: [],
        actions: [],
      }))
      .mockResolvedValueOnce(jsonResponse({
        generated_by: "deterministic",
        analysis: {
          verdict: "NEGOTIATE",
          summary: "The prices are close.",
          you_give: { players: ["Mine Back"], positions: ["RB"], projected_points: 8, season_points: 40, injured: [] },
          you_receive: { players: ["Their Back"], positions: ["RB"], projected_points: 14, season_points: 50, injured: [] },
          roster_impact: [],
          lineup_impact: [],
          risks: [],
          data_gaps: [],
        },
      }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <TradeOffer leagueId="league-1" mine={roster("mine", "Us", "Mine Back")} opponent={roster("opp-1", "Rivals", "Their Back")} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByTestId("ask-trade"));
    expect(await screen.findByTestId("trade-advice")).toHaveTextContent("Give Bench Receiver");
    const asked = JSON.parse(String(fetchMock.mock.calls[0][1].body));
    expect(asked.messages[0].content).toContain("team_id opp-1");

    await user.click(screen.getByText("Mine Back"));
    await user.click(screen.getByText("Their Back"));
    await user.click(screen.getByTestId("analyze-offer"));
    expect(await screen.findByTestId("trade-result")).toHaveTextContent("NEGOTIATE");
  });
});
