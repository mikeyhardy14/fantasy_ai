import { PlayerSheetDialog } from "@/components/player-sheet";
import type { PlayerSheet } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import { player } from "./fixtures";

const sheet: PlayerSheet = {
  player: player({
    name: "Quinn Arrow",
    projected_points: 10,
    projection_reasons: ["10 adds up the DraftKings prop lines using this league's scoring."],
    projection_lines: [{ label: "Rush yds", line: 100.5, weight: 0.1, points: 10.05 }],
  }),
  recent_games: [
    {
      week: 3,
      opponent: "LV",
      home: false,
      fantasy_points: 19.4,
      points_label: "This league",
      summary: "280 pass yds, 2 pass TD",
      stats: { pass_yd: 280, pass_td: 2 },
    },
  ],
  games_note: null,
};

describe("PlayerSheetDialog", () => {
  it("shows the prop math and recent stats in tables", () => {
    render(<PlayerSheetDialog sheet={sheet} loading={false} error={null} onClose={() => undefined} />);
    expect(screen.getByText("Quinn Arrow")).toBeInTheDocument();
    expect(screen.getByText(/40\.1 total/)).toBeInTheDocument();
    expect(screen.getByText("Rush yds")).toBeInTheDocument();
    expect(screen.getByText("100.5")).toBeInTheDocument();
    expect(screen.getByText("10.05")).toBeInTheDocument();
    expect(screen.getByText("Pass yds")).toBeInTheDocument();
    expect(screen.getByText("Pass TD")).toBeInTheDocument();
    expect(screen.getByText("280")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("@ LV")).toBeInTheDocument();
    expect(screen.getByText("19.4")).toBeInTheDocument();
    expect(screen.getByText("Points: This league.")).toBeInTheDocument();
  });
});
