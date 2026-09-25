import { MatchupSlate } from "@/components/matchup-slate";
import type { LeagueMatchup, MatchupSide } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player, slot } from "./fixtures";

function side(name: string, id: string, points: number): MatchupSide {
  return {
    team: {
      id,
      name,
      owner_name: null,
      avatar: null,
      wins: 2,
      losses: 1,
      ties: 0,
      record: "2-1",
      points_for: 300,
      points_against: 280,
      faab_remaining: null,
      waiver_position: null,
      is_user_team: false,
    },
    points,
    projected_points: 110,
    starters: [slot({ slot: "QB", player: player({ name: `${name} QB`, position: "QB" }) })],
  };
}

function game(left: string, right: string, yours = false): LeagueMatchup {
  return {
    week: 4,
    is_bye: false,
    involves_user: yours,
    status: "upcoming",
    team: side(left, left, yours ? 10 : 88),
    opponent: side(right, right, yours ? 12 : 91),
  };
}

describe("MatchupSlate", () => {
  it("lists the other games and opens their starters", async () => {
    const user = userEvent.setup();
    render(<MatchupSlate games={[game("Gridiron Gurus", "Rivals", true), game("Touchdown Titans", "Blitz Brigade")]} week={4} />);
    expect(screen.queryByText("Gridiron Gurus")).not.toBeInTheDocument();
    expect(screen.getByText("Touchdown Titans")).toBeInTheDocument();
    expect(screen.getByText("Blitz Brigade")).toBeInTheDocument();
    expect(screen.queryByText("Touchdown Titans QB")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Starters" }));
    expect(screen.getByText("Touchdown Titans QB")).toBeInTheDocument();
    expect(screen.getByText("Blitz Brigade QB")).toBeInTheDocument();
  });
});
