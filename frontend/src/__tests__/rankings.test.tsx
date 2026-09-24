import { RankingsTable } from "@/components/rankings-table";
import type { Rankings } from "@/lib/types";
import { render, screen } from "@testing-library/react";

const rankings: Rankings = {
  week: 3,
  notes: [
    "Implied team points use DraftKings. One line is posted per game, so this is not an average of several books.",
    "Team play counts, recent usage shares, player props, and floor and ceiling simulations are not in these ranks.",
  ],
  rows: [
    {
      rank: 1,
      player_id: "p1",
      name: "Quinn Arrow",
      position: "QB",
      nfl_team: "KC",
      opponent: "LV",
      home: true,
      headshot_url: null,
      injury_status: null,
      total: 47,
      spread: -3,
      implied_points: 25,
      win_probability: 0.68,
      book_count: 1,
      books: ["DraftKings"],
      projected_points: 17.3,
      projection_source: "vegas",
      vorp: 4.2,
    },
  ],
};

describe("RankingsTable", () => {
  it("shows the implied total, win probability, projection, and value", () => {
    render(<RankingsTable rankings={rankings} />);
    expect(screen.getByText("Quinn Arrow")).toBeInTheDocument();
    expect(screen.getByText("25.0")).toBeInTheDocument();
    expect(screen.getByText("O/U 47 · -3")).toBeInTheDocument();
    expect(screen.getByText("vs LV")).toBeInTheDocument();
    expect(screen.getByText("68%")).toBeInTheDocument();
    expect(screen.getByText("17.3")).toBeInTheDocument();
    expect(screen.getByText("+4.2")).toBeInTheDocument();
  });
});
