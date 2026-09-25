import { SeasonStrip } from "@/components/player-face";
import type { ScheduleGame } from "@/lib/types";
import { render, screen } from "@testing-library/react";

function game(week: number, opponent: string): ScheduleGame {
  return { week, opponent, home: true, spread: null, total: null, implied_points: null };
}

describe("SeasonStrip", () => {
  it("shows only the current week and the one after it", () => {
    render(
      <SeasonStrip
        week={4}
        games={[game(1, "BUF"), game(2, "DAL"), game(4, "KC"), game(5, "DEN"), game(6, "LV")]}
      />,
    );
    expect(screen.getByText("4 vs KC")).toBeInTheDocument();
    expect(screen.getByText("5 vs DEN")).toBeInTheDocument();
    expect(screen.queryByText("6 vs LV")).toBeNull();
    expect(screen.queryByText("1 vs BUF")).toBeNull();
  });
});
