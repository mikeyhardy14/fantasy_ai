import { PlayerTable } from "@/components/player-table";
import { rosterPlayers, WaiverAddDialog } from "@/components/waiver-add";
import type { Team } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player, slot } from "./fixtures";

const added = player({ id: "free", name: "Free Agent", position: "RB", projected_points: 12 });

describe("WaiverAddDialog", () => {
  it("drops the chosen player and leaves the add alone when cancelled", async () => {
    const user = userEvent.setup();
    const onDrop = vi.fn();
    const onKeep = vi.fn();
    const onCancel = vi.fn();
    const roster = [
      slot({ slot: "BN", slot_index: null, is_starter: false, player: player({ id: "bench", name: "Bench Receiver", position: "WR", projected_points: 4.1 }) }),
      slot({ slot: "QB", slot_index: 0, is_starter: true, player: player({ id: "qb", name: "Quinn Arrow", position: "QB", projected_points: 18 }) }),
    ];
    render(
      <WaiverAddDialog
        player={added}
        roster={roster}
        dropRequired
        pending={false}
        error={null}
        onDrop={onDrop}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Add Free Agent" })).toBeInTheDocument();
    expect(screen.queryByTestId("waiver-keep")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("waiver-drop")[0]).toHaveTextContent("Bench Receiver");
    await user.click(screen.getByRole("button", { name: /Drop Bench Receiver/ }));
    expect(onDrop).toHaveBeenCalledWith("bench");
    await user.click(screen.getByTestId("waiver-cancel"));
    expect(onCancel).toHaveBeenCalled();
    expect(onKeep).not.toHaveBeenCalled();
  });

  it("can add without a drop when the roster has room", async () => {
    const user = userEvent.setup();
    const onKeep = vi.fn();
    render(
      <WaiverAddDialog
        player={added}
        roster={[slot({ player: player({ id: "bench", name: "Bench Receiver" }) })]}
        dropRequired={false}
        pending={false}
        error={null}
        onDrop={vi.fn()}
        onKeep={onKeep}
        onCancel={vi.fn()}
      />,
    );
    await user.click(screen.getByTestId("waiver-keep"));
    expect(onKeep).toHaveBeenCalled();
  });
});

describe("rosterPlayers", () => {
  it("lists drop candidates in lineup order", () => {
    const names = rosterPlayers({
      starters: [
        slot({ slot: "RB", slot_index: 1, player: player({ id: "rb", name: "Run Back", projected_points: 8 }) }),
        slot({ slot: "QB", slot_index: 0, player: player({ id: "qb", name: "Quinn Arrow", projected_points: 22 }) }),
      ],
      bench: [
        slot({ slot: "BN", slot_index: null, is_starter: false, player: player({ id: "bench", name: "Bench Receiver", projected_points: 3 }) }),
      ],
      reserve: [
        slot({ slot: "TAXI", slot_index: null, is_starter: false, player: player({ id: "taxi", name: "Taxi Rookie", projected_points: 1 }) }),
        slot({ slot: "IR", slot_index: null, is_starter: false, player: player({ id: "ir", name: "Hurt Starter", projected_points: 20 }) }),
      ],
    } as Team).map((row) => row.player?.name);

    expect(names).toEqual(["Quinn Arrow", "Run Back", "Bench Receiver", "Hurt Starter", "Taxi Rookie"]);
  });
});

describe("PlayerTable add", () => {
  it("opens an add from the waiver list", async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    render(<PlayerTable players={[added]} onAdd={onAdd} week={4} />);
    await user.click(screen.getByTestId("waiver-add"));
    expect(onAdd).toHaveBeenCalledWith(added);
  });
});
