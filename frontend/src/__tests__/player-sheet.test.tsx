import { PlayerSheetDialog } from "@/components/player/player-sheet";
import type { PlayerSheet } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    expect(screen.getByTestId("rostered-on")).toHaveTextContent("Free agent");
  });

  it("names the fantasy team and sends the offer the assistant wrote", async () => {
    const user = userEvent.setup();
    const onTradeFor = vi.fn();
    const onSend = vi.fn();
    render(
      <PlayerSheetDialog
        sheet={{
          ...sheet,
          rostered_on: { team_id: "rival", team_name: "Rival", owner_name: "Casey", is_user_team: false },
        }}
        loading={false}
        error={null}
        onClose={() => undefined}
        canAct
        onTradeFor={onTradeFor}
        canSend
        onSend={onSend}
        tradeDraft={{
          give: [{ id: "give", name: "Bench Receiver", position: "WR" }],
          receive: [{ id: "get", name: "Quinn Arrow", position: "QB" }],
          opponent_name: "Rival",
          message: "Offer Bench Receiver to Rival for Quinn Arrow.",
        }}
      />,
    );
    expect(screen.getByTestId("rostered-on")).toHaveTextContent("On Rival · Casey");
    await user.click(screen.getByTestId("trade-for"));
    expect(onTradeFor).toHaveBeenCalled();
    expect(screen.getByTestId("trade-draft")).toHaveTextContent("Offer Bench Receiver to Rival for Quinn Arrow.");
    await user.click(screen.getByTestId("trade-send"));
    expect(onSend).toHaveBeenCalled();
  });

  it("offers add and a waiver pickup for a free agent", async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    const onWaiver = vi.fn();
    render(<PlayerSheetDialog sheet={sheet} loading={false} error={null} onClose={() => undefined} canAct onAdd={onAdd} onWaiver={onWaiver} />);
    await user.click(screen.getByTestId("player-add"));
    await user.click(screen.getByTestId("player-waiver"));
    expect(onAdd).toHaveBeenCalled();
    expect(onWaiver).toHaveBeenCalled();
    expect(screen.queryByTestId("player-drop")).toBeNull();
  });

  it("offers a drop and a trade for a player on your team", async () => {
    const user = userEvent.setup();
    const onDrop = vi.fn();
    const onConfirmDrop = vi.fn();
    const onTrade = vi.fn();
    render(
      <PlayerSheetDialog
        sheet={{ ...sheet, rostered_on: { team_id: "mine", team_name: "Mine", owner_name: "You", is_user_team: true } }}
        loading={false}
        error={null}
        onClose={() => undefined}
        canAct
        onDrop={onDrop}
        confirmDrop
        onConfirmDrop={onConfirmDrop}
        onTrade={onTrade}
      />,
    );
    expect(screen.queryByTestId("player-add")).toBeNull();
    await user.click(screen.getByTestId("player-drop"));
    expect(onDrop).toHaveBeenCalled();
    await user.click(screen.getByTestId("player-drop-confirm"));
    expect(onConfirmDrop).toHaveBeenCalled();
    await user.click(screen.getByTestId("player-trade"));
    expect(onTrade).toHaveBeenCalled();
  });
});
