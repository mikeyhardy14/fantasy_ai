import { OutstandingTrades } from "@/components/outstanding-trades";
import { render, screen } from "@testing-library/react";

const user = "team-me";

describe("OutstandingTrades", () => {
  it("lists a pending offer with the players each side would move", () => {
    render(
      <OutstandingTrades
        userTeamId={user}
        userTeamName="Mike's Marauders"
        trades={[
          {
            id: "open",
            type: "trade",
            status: "pending",
            week: 4,
            created_at: new Date().toISOString(),
            team_names: ["Mike's Marauders", "Rival"],
            faab_bid: null,
            involves_user: true,
            adds: [
              { player_id: "a", player_name: "Opp RunnerOne", position: "RB", team_id: user, team_name: "Mike's Marauders", headshot_url: null },
              { player_id: "b", player_name: "Bench Receiver", position: "WR", team_id: "team-them", team_name: "Rival", headshot_url: null },
            ],
            drops: [
              { player_id: "b", player_name: "Bench Receiver", position: "WR", team_id: user, team_name: "Mike's Marauders", headshot_url: null },
              { player_id: "a", player_name: "Opp RunnerOne", position: "RB", team_id: "team-them", team_name: "Rival", headshot_url: null },
            ],
          },
          {
            id: "done",
            type: "trade",
            status: "complete",
            week: 2,
            created_at: new Date().toISOString(),
            team_names: ["Mike's Marauders", "Rival"],
            faab_bid: null,
            involves_user: true,
            adds: [],
            drops: [],
          },
        ]}
      />,
    );
    const offer = screen.getByTestId("outstanding-trade");
    expect(offer).toHaveTextContent("Offer to Rival");
    expect(offer).toHaveTextContent("Pending");
    expect(offer).toHaveTextContent("Bench Receiver");
    expect(offer).toHaveTextContent("Opp RunnerOne");
    expect(screen.queryByText(/week 2/i)).not.toBeInTheDocument();
  });
});
