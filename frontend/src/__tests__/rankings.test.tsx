import { RankingsTable } from "@/components/rankings-table";
import type { Rankings, Team } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player, slot } from "./fixtures";

const rankings: Rankings = {
  week: 3,
  notes: [],
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
      season_points: 88.4,
      vorp: 4.2,
    },
  ],
};

describe("RankingsTable", () => {
  it("shows the implied total, win probability, projection, and value", () => {
    render(<RankingsTable rankings={rankings} />);
    expect(screen.getByText("Quinn Arrow")).toBeInTheDocument();
    expect(screen.queryByText(/Implied team points/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Showing the top/)).not.toBeInTheDocument();
    expect(screen.getByText("25.0")).toBeInTheDocument();
    expect(screen.getByText("O/U 47 · -3")).toBeInTheDocument();
    expect(screen.getByText("vs LV")).toBeInTheDocument();
    expect(screen.getByText("68%")).toBeInTheDocument();
    expect(screen.getByText("17.3")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "88.4" })).toBeInTheDocument();
    expect(screen.getByText("+4.2")).toBeInTheDocument();
    expect(screen.queryByTestId("rank-sub")).toBeNull();
  });

  it("subs the higher-projected backup into a rostered starter", async () => {
    const starter = player({ id: "p1", name: "Quinn Arrow", position: "QB", fantasy_positions: ["QB"], projected_points: 17.3 });
    const low = player({ id: "qb-low", name: "Low Arm", position: "QB", fantasy_positions: ["QB"], projected_points: 4 });
    const high = player({ id: "qb-high", name: "High Arm", position: "QB", fantasy_positions: ["QB"], projected_points: 12 });
    const roster: Team = {
      team: {
        id: "team-1",
        name: "Studs",
        owner_name: "Mike",
        avatar: null,
        wins: 1,
        losses: 1,
        ties: 0,
        record: "1-1",
        points_for: 100,
        points_against: 90,
        faab_remaining: 100,
        waiver_position: 1,
        is_user_team: true,
      },
      week: 3,
      starters: [slot({ slot: "QB", slot_index: 0, player: starter })],
      bench: [
        slot({ slot: "BN", slot_index: null, is_starter: false, player: low }),
        slot({ slot: "BN", slot_index: null, is_starter: false, player: high }),
      ],
      reserve: [],
      lineup_slots: ["QB"],
      lineup_issues: [],
      projected_points: 17.3,
      projection_coverage: "partial",
    };
    const onMove = vi.fn();
    const user = userEvent.setup();
    render(<RankingsTable rankings={rankings} roster={roster} onMove={onMove} />);
    await user.click(screen.getByTestId("rank-sub"));
    const choices = screen.getAllByTestId("rank-sub-choice");
    expect(choices[0]).toHaveTextContent("Sub in High Arm");
    expect(choices[0]).toHaveTextContent("12.0 proj");
    expect(choices[1]).toHaveTextContent("Sub in Low Arm");
    await user.click(choices[0]);
    expect(onMove).toHaveBeenCalledWith(expect.objectContaining({ playerId: "qb-high", destination: "starter", slotIndex: 0 }));
  });

  it("highlights a player you own and adds a player nobody owns", async () => {
    const rows: Rankings = {
      ...rankings,
      rows: [
        { ...rankings.rows[0], owned: "you" },
        { ...rankings.rows[0], rank: 2, player_id: "fa", name: "Free Agent", owned: null },
        { ...rankings.rows[0], rank: 3, player_id: "other", name: "Other Owner", owned: "league" },
      ],
    };
    const onAdd = vi.fn();
    const user = userEvent.setup();
    render(<RankingsTable rankings={rows} onAdd={onAdd} />);

    const yours = screen.getByText("Quinn Arrow").closest("tr");
    expect(yours).toHaveAttribute("data-owned", "you");
    expect(yours).toHaveTextContent("Yours");
    expect(screen.getByText("Other Owner").closest("tr")).toHaveAttribute("data-owned", "league");
    expect(screen.getAllByTestId("rank-add")).toHaveLength(1);

    await user.click(screen.getByTestId("rank-add"));
    expect(onAdd).toHaveBeenCalledWith("fa");
  });
});
