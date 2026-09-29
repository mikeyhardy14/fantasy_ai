import { MatchupCompare } from "@/components/matchup/matchup-compare";
import type { NflGame } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import { player, slot } from "./fixtures";

const pregame = [{ week: 4, opponent: "BUF", home: true, spread: -3, total: 47, implied_points: 25, state: "pre" as const }];

const game: NflGame = {
  away: "BUF",
  home: "KC",
  away_score: 10,
  home_score: 7,
  state: "in",
  detail: "8:22 - 2nd",
  summary: "Pass complete.",
  broadcast: null,
};

describe("MatchupCompare", () => {
  it("shows how often the projected starter outscores the other", () => {
    render(
      <MatchupCompare
        week={4}
        yours={[slot({ slot: "WR", slot_index: 2, player: player({ name: "Wide One", projected_points: 16, schedule: pregame }) })]}
        theirs={[slot({ slot: "WR", slot_index: 2, player: player({ name: "Wide Two", projected_points: 11, schedule: pregame }) })]}
        yourName="Us"
        theirName="Them"
        calls={[{ slot_index: 2, start_name: "Wide One", win_prob: 0.64, confidence: "start" }]}
      />,
    );
    expect(screen.getByTestId("start-call")).toHaveTextContent("64% start");
    expect(screen.getByLabelText("You are ahead")).toBeInTheDocument();
    expect(screen.getByTestId("edge")).toHaveTextContent("5.0");
  });

  it("hides the range once the game has started", () => {
    const live = [{ ...pregame[0], state: "in" as const }];
    render(
      <MatchupCompare
        week={4}
        yours={[slot({ slot: "WR", slot_index: 2, player: player({ name: "Wide One", schedule: live }), points: 8 })]}
        theirs={[slot({ slot: "WR", slot_index: 2, player: player({ name: "Wide Two", schedule: pregame }) })]}
        yourName="Us"
        theirName="Them"
        games={[game]}
        calls={[{ slot_index: 2, start_name: "Wide One", win_prob: 0.64, confidence: "start" }]}
      />,
    );
    expect(screen.getByTestId("matchup-row")).toHaveAttribute("data-live", "true");
    expect(screen.getByTestId("matchup-row")).toHaveClass("bg-amber-400/10");
    expect(screen.queryByTestId("start-call")).toBeNull();
    expect(screen.getAllByTestId("point-status")[0]).toHaveTextContent("8:22 - 2nd");
  });

  it("shows the counting line and the clock while that player is in a game", () => {
    const live = [{ ...pregame[0], state: "in" as const }];
    render(
      <MatchupCompare
        week={4}
        yours={[slot({ slot: "RB", slot_index: 1, player: player({ name: "Live Back", nfl_team: "KC", schedule: live }), points: 9.4, stat_line: "64 rush yds, 1 rush TD" })]}
        theirs={[slot({ slot: "RB", slot_index: 1, player: player({ name: "Waiting", nfl_team: "DAL", schedule: pregame }) })]}
        yourName="Us"
        theirName="Them"
        games={[game]}
      />,
    );
    expect(screen.getByTestId("live-stats")).toHaveTextContent("64 rush yds, 1 rush TD");
    expect(screen.getByText("8:22 - 2nd")).toBeInTheDocument();
    expect(screen.queryByText(/^pts$/i)).toBeNull();
  });

  it("marks the side that has the ball as on the field", () => {
    const live = [{ ...pregame[0], state: "in" as const }];
    render(
      <MatchupCompare
        week={4}
        yours={[
          slot({ slot: "WR", slot_index: 2, player: player({ name: "On Ball", nfl_team: "KC", position: "WR", schedule: live }) }),
          slot({ slot: "DEF", slot_index: 8, player: player({ name: "Chiefs D", nfl_team: "KC", position: "DEF", schedule: live }) }),
        ]}
        theirs={[
          slot({ slot: "WR", slot_index: 2, player: player({ name: "Waiting", nfl_team: "DAL", position: "WR", schedule: [{ ...pregame[0], state: "pre" }] }) }),
          slot({ slot: "DEF", slot_index: 8, player: player({ name: "Done D", nfl_team: "LAR", position: "DEF", schedule: [{ ...pregame[0], state: "post" }] }) }),
        ]}
        yourName="Us"
        theirName="Them"
        games={[
          { ...game, possession: "KC" },
          { away: "DAL", home: "PHI", away_score: null, home_score: null, state: "pre", detail: "Sun 1:00", summary: null, broadcast: null },
          { away: "SEA", home: "LAR", away_score: 3, home_score: 20, state: "post", detail: "Final", summary: null, broadcast: null },
        ]}
      />,
    );
    const marks = screen.getAllByTestId("play-status");
    expect(marks.find((mark) => mark.textContent === "On field")).toBeTruthy();
    expect(marks.filter((mark) => mark.textContent === "In game").length).toBeGreaterThan(0);
    expect(marks.find((mark) => mark.textContent === "Yet to play")).toBeTruthy();
    expect(marks.find((mark) => mark.textContent === "Final")).toBeTruthy();
    expect(screen.getAllByTestId("matchup-row")[0]).toHaveAttribute("data-phase", "field");
  });

  it("says Final under the points once that game is over this week", () => {
    const done = [{ ...pregame[0], state: "post" as const }];
    render(
      <MatchupCompare
        week={4}
        yours={[slot({ slot: "RB", slot_index: 1, player: player({ name: "Done Back", nfl_team: "KC", schedule: done }), points: 18.2 })]}
        theirs={[slot({ slot: "RB", slot_index: 1, player: player({ name: "Other", nfl_team: "DAL", schedule: pregame }) })]}
        yourName="Us"
        theirName="Them"
        games={[{ ...game, state: "post", detail: "Final" }]}
      />,
    );
    expect(screen.getAllByText("Final").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("live-stats")).toBeNull();
    expect(screen.queryByText("8:22 - 2nd")).toBeNull();
  });

  it("leaves the points unlabeled on a previous week", () => {
    const done = [{ ...pregame[0], state: "post" as const }];
    render(
      <MatchupCompare
        week={3}
        current={false}
        yours={[slot({ slot: "RB", slot_index: 1, player: player({ name: "Done Back", nfl_team: "KC", schedule: done }), points: 18.2, stat_line: "64 rush yds" })]}
        theirs={[slot({ slot: "RB", slot_index: 1, player: player({ name: "Other", nfl_team: "BUF", schedule: done }), points: 11 })]}
        yourName="Us"
        theirName="Them"
        games={[{ ...game, state: "post", detail: "Final" }]}
      />,
    );
    expect(screen.getByText("18.2")).toBeInTheDocument();
    expect(screen.queryByTestId("point-status")).toBeNull();
    expect(screen.queryByTestId("live-stats")).toBeNull();
    expect(screen.queryByText("Final")).toBeNull();
  });

  it("washes a bye row muted and an out row red", () => {
    render(
      <MatchupCompare
        week={4}
        current={false}
        yours={[
          slot({ slot: "RB", slot_index: 1, flags: ["BYE"], player: player({ name: "Bye Back" }) }),
          slot({ slot: "WR", slot_index: 2, flags: ["OUT"], player: player({ name: "Out Wide" }) }),
        ]}
        theirs={[
          slot({ slot: "RB", slot_index: 1, player: player({ name: "Other Back" }) }),
          slot({ slot: "WR", slot_index: 2, player: player({ name: "Other Wide" }) }),
        ]}
        yourName="Us"
        theirName="Them"
      />,
    );
    const rows = screen.getAllByTestId("matchup-row");
    expect(rows[0]).toHaveClass("bg-slate-500/10");
    expect(rows[1]).toHaveClass("bg-red-500/10");
  });
});