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
  it("benches a starter and hides IR when he is not eligible", async () => {
    const onMove = vi.fn();
    const user = userEvent.setup();
    render(<LineupBoard team={team} irCapacity={1} pending={false} notice={null} onMove={onMove} />);

    await user.click(screen.getByRole("button", { name: "Move Quinn Arrow" }));
    expect(screen.getByRole("menuitem", { name: "Bench" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "IR" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "IR full" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Bench" }));
    expect(onMove).toHaveBeenCalledWith({ playerId: "qb-1", destination: "bench", slotIndex: undefined });
  });

  it("offers IR only for a designation this league allows", async () => {
    const onMove = vi.fn();
    const user = userEvent.setup();
    const out = player({ id: "rb-out", name: "Out Back", position: "RB", fantasy_positions: ["RB"], injury_status: "Out" });
    render(
      <LineupBoard
        team={{ ...team, bench: [slot({ slot: "BN", slot_index: null, is_starter: false, player: out, points: null })] }}
        irCapacity={2}
        irRules={{ out: true }}
        pending={false}
        notice={null}
        onMove={onMove}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Move Out Back" }));
    expect(screen.getByRole("menuitem", { name: "IR" })).toBeInTheDocument();
  });

  it("shows the player being subbed, their position color, and who they replace", async () => {
    const onMove = vi.fn();
    const user = userEvent.setup();
    const incumbent = player({ id: "rb-2", name: "Starter Back", position: "RB", fantasy_positions: ["RB"], headshot_url: "https://example.com/starter.png" });
    render(
      <LineupBoard
        team={{
          ...team,
          starters: [
            slot({ slot: "QB", slot_index: 0, player: starter, points: 18 }),
            slot({ slot: "RB", slot_index: 1, player: incumbent, points: 12 }),
          ],
        }}
        irCapacity={1}
        pending={false}
        notice={null}
        onMove={onMove}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Move Backup Back" }));
    const moving = screen.getByTestId("sub-player");
    expect(moving).toHaveTextContent("Backup Back");
    expect(moving.querySelector("[data-testid='position-badge']")).toHaveClass("text-brand");
    const replace = screen.getByRole("menuitem", { name: "Start at RB, replace Starter Back" });
    expect(replace).toHaveTextContent("Starter Back");
    expect(replace.querySelector("img")).toHaveAttribute("src", "https://example.com/starter.png");
    expect(replace.querySelector(".text-brand")).toHaveTextContent("RB");
  });

  it("subs a bench player in from the starting lineup", async () => {
    const onMove = vi.fn();
    const user = userEvent.setup();
    const backupQb = player({
      id: "qb-2",
      name: "Backup Arm",
      position: "QB",
      fantasy_positions: ["QB"],
      headshot_url: "https://example.com/qb.png",
    });
    render(
      <LineupBoard
        team={{ ...team, bench: [slot({ slot: "BN", slot_index: null, is_starter: false, player: backupQb, points: null }), ...team.bench] }}
        irCapacity={1}
        pending={false}
        notice={null}
        onMove={onMove}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Move Quinn Arrow" }));
    const sub = screen.getByRole("menuitem", { name: "Sub in Backup Arm" });
    expect(sub).toHaveTextContent("14.2 proj");
    expect(sub.querySelector("img")).toHaveAttribute("src", "https://example.com/qb.png");
    expect(sub.querySelector(".text-rose-300")).toHaveTextContent("QB");
    await user.click(sub);
    expect(onMove).toHaveBeenCalledWith({ playerId: "qb-2", destination: "starter", slotIndex: 0 });
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
