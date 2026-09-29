import { NflSlate } from "@/components/matchup/nfl-slate";
import type { NflGame } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const live: NflGame = {
  away: "ATL",
  home: "GB",
  away_score: 17,
  home_score: 7,
  state: "in",
  detail: "12:08 - 3rd",
  summary: "Official Timeout at 12:08 · 1st & 10 at ATL 16",
  broadcast: "Prime Video",
  venue: "Green Bay, WI",
  broadcast_market: "national",
};

describe("NflSlate", () => {
  it("shows the live score, clock, and latest play", () => {
    render(<NflSlate games={[live]} />);
    expect(screen.getByTestId("nfl-game")).toHaveClass("bg-red-500/10");
    expect(screen.getByText("ATL 17, GB 7")).toBeInTheDocument();
    expect(screen.getByAltText("ATL logo")).toBeInTheDocument();
    expect(screen.getByAltText("GB logo")).toBeInTheDocument();
    expect(screen.getByAltText("Prime Video logo")).toBeInTheDocument();
    expect(screen.getByText(/National · Green Bay, WI/)).toBeInTheDocument();
    expect(screen.getByText(/Live/)).toBeInTheDocument();
    expect(screen.getByText("12:08 - 3rd")).toBeInTheDocument();
    expect(screen.getByText(/Official Timeout at 12:08/)).toBeInTheDocument();
  });

  it("opens a game for the score and latest play", async () => {
    const user = userEvent.setup();
    render(<NflSlate games={[live]} compact />);
    expect(screen.queryByText(/Official Timeout at 12:08/)).not.toBeInTheDocument();
    await user.click(screen.getByTestId("nfl-game"));
    expect(screen.getByTestId("nfl-game-detail")).toHaveTextContent("ATL 17, GB 7");
    expect(screen.getByText(/Official Timeout at 12:08/)).toBeInTheDocument();
  });
});
