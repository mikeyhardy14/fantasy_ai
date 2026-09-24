import { LineupBoard } from "@/components/lineup-board";
import type { Team } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player, slot } from "./fixtures";

const starter = player({ id: "qb-1", name: "Quinn Arrow", position: "QB", fantasy_positions: ["QB"] });
const bench = player({ id: "rb-1", name: "Backup Back", position: "RB", fantasy_positions: ["RB"] });
const injured = player({ id: "wr-1", name: "Hurt Hands", position: "WR", fantasy_positions: ["WR"] });

const team: Team = {
  team: {
    id: "team-1",
    name: "Mike's Marauders",
    owner_name: "Mike",
    avatar: null,
    wins: 2,
    losses: 1,
    ties: 0,
    record: "2-1",
    points_for: 300,
    points_against: 280,
    faab_remaining: 80,
    waiver_position: 4,
    is_user_team: true,
  },
  week: 4,
  starters: [slot({ slot: "QB", slot_index: 0, player: starter, points: 18 })],
  bench: [slot({ slot: "BN", slot_index: null, is_starter: false, player: bench, points: null })],
  reserve: [slot({ slot: "IR", slot_index: null, is_starter: false, player: injured, points: null })],
  lineup_slots: ["QB", "RB"],
  lineup_issues: [],
  projected_points: 18,
  projection_coverage: "partial",
};

describe("LineupBoard", () => {
  it("benches a starter from the slot box and offers IR", async () => {
    const onMove = vi.fn();
    const user = userEvent.setup();
    render(<LineupBoard team={team} irCapacity={1} pending={false} notice={null} onMove={onMove} />);

    await user.click(screen.getByRole("button", { name: "Move Quinn Arrow" }));
    expect(screen.getByRole("menuitem", { name: "Bench" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "IR full" })).toBeDisabled();
    await user.click(screen.getByRole("menuitem", { name: "Bench" }));
    expect(onMove).toHaveBeenCalledWith({ playerId: "qb-1", destination: "bench", slotIndex: undefined });
  });

  it("starts a bench player in an open eligible slot from the slot box", async () => {
    const onMove = vi.fn();
    const user = userEvent.setup();
    render(<LineupBoard team={team} irCapacity={1} pending={false} notice={null} onMove={onMove} />);

    await user.click(screen.getByRole("button", { name: "Move Backup Back" }));
    await user.click(screen.getByRole("menuitem", { name: "Start at RB" }));
    expect(onMove).toHaveBeenCalledWith({ playerId: "rb-1", destination: "starter", slotIndex: 1 });
  });
});
