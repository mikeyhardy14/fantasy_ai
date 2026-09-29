import { DepthChart } from "@/components/player/depth-chart";
import type { GameLook, RankingRow } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

const game: GameLook = {
  projected_points: 18,
  points: 12.4,
  stat_line: "80 rush yds",
  opponent: "LV",
  home: true,
  away: "LV",
  home_team: "KC",
  away_score: 10,
  home_score: 17,
  state: "in",
  clock: "Q3 8:12",
};

function row(name: string, position: string): RankingRow {
  return {
    rank: 1,
    player_id: name,
    name,
    position,
    nfl_team: "KC",
    opponent: "LV",
    home: true,
    headshot_url: null,
    injury_status: null,
    total: 47,
    spread: -3,
    implied_points: 25,
    win_probability: null,
    book_count: 0,
    books: [],
    projected_points: 14,
    projection_source: null,
    season_points: 40,
    vorp: 1,
    game,
  };
}

describe("DepthChart", () => {
  it("shows the team game once and leaves scores off the player rows", () => {
    render(<DepthChart team="KC" rows={[row("Patrick Mahomes", "QB"), row("Isiah Pacheco", "RB")]} />);
    expect(screen.getAllByTestId("team-game")).toHaveLength(1);
    expect(screen.getByTestId("team-game")).toHaveTextContent("LV 10, KC 17");
    expect(screen.getByTestId("team-game")).toHaveTextContent("Q3 8:12");
    expect(screen.queryByTestId("player-game")).not.toBeInTheDocument();
    expect(screen.queryByText("80 rush yds")).not.toBeInTheDocument();
    expect(screen.getByText("Patrick Mahomes")).toBeInTheDocument();
    expect(screen.getByText("Isiah Pacheco")).toBeInTheDocument();
  });
});
