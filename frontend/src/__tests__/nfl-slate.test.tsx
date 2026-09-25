import { NflSlate } from "@/components/nfl-slate";
import type { NflGame } from "@/lib/types";
import { render, screen } from "@testing-library/react";

const live: NflGame = {
  away: "ATL",
  home: "GB",
  away_score: 17,
  home_score: 7,
  state: "in",
  detail: "12:08 - 3rd",
  summary: "Official Timeout at 12:08 · 1st & 10 at ATL 16",
  broadcast: "Prime Video",
};

describe("NflSlate", () => {
  it("shows the live score, clock, and latest play", () => {
    render(<NflSlate games={[live]} />);
    expect(screen.getByTestId("nfl-game")).toHaveClass("bg-red-500/10");
    expect(screen.getByText("ATL 17, GB 7")).toBeInTheDocument();
    expect(screen.getByText(/Live/)).toBeInTheDocument();
    expect(screen.getByText("12:08 - 3rd")).toBeInTheDocument();
    expect(screen.getByText(/Official Timeout at 12:08/)).toBeInTheDocument();
  });
});
