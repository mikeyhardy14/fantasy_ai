import { LeagueRosterBoard } from "@/components/league-rosters";
import type { Team } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import { player, slot } from "./fixtures";

function team(name: string, yours: boolean): Team {
  return {
    team: {
      id: yours ? "mine" : "theirs",
      name,
      owner_name: yours ? "You" : "Rival",
      avatar: null,
      wins: 2,
      losses: 1,
      ties: 0,
      record: "2-1",
      points_for: 300,
      points_against: 280,
      faab_remaining: 80,
      waiver_position: 4,
      is_user_team: yours,
    },
    week: 4,
    starters: [slot({ slot: "QB", player: player({ name: yours ? "Quinn Arrow" : "Rex Cannon", position: "QB" }) })],
    bench: [slot({ slot: "BN", slot_index: null, is_starter: false, player: player({ name: yours ? "Bench Back" : "Opp Runner", position: "RB" }) })],
    reserve: [],
    lineup_slots: ["QB"],
    lineup_issues: [],
    projected_points: 110,
    projection_coverage: "full",
  };
}

describe("LeagueRosterBoard", () => {
  it("shows every roster and links to the other team", () => {
    render(<LeagueRosterBoard teams={[team("Gridiron Gurus", true), team("Touchdown Titans", false)]} week={4} />);
    expect(screen.getByText("Quinn Arrow")).toBeInTheDocument();
    expect(screen.getByText("Rex Cannon")).toBeInTheDocument();
    expect(screen.getByText("Opp Runner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2. Touchdown Titans" })).toHaveAttribute("href", "/teams/theirs");
    expect(screen.getByRole("link", { name: "1. Gridiron Gurus" })).toHaveAttribute("href", "/team");
  });
});
