import { LeagueGames, MatchupSlate } from "@/components/matchup/matchup-slate";
import type { LeagueMatchup, MatchupSide } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player, slot } from "./fixtures";

function game(left: string, right: string, yours = false): LeagueMatchup {
  return {
    week: 4,
    is_bye: false,
    involves_user: yours,
    status: "upcoming",
    team: side(left, left, yours ? 10 : 88, `${left} QB`, yours ? 22 : 8),
    opponent: side(right, right, yours ? 12 : 91, `${right} QB`, yours ? 6 : 28),
  };
}

function side(name: string, id: string, points: number, playerName: string, playerPoints: number): MatchupSide {
  return {
    team: {
      id,
      name,
      owner_name: null,
      avatar: null,
      wins: 2,
      losses: 1,
      ties: 0,
      record: "2-1",
      points_for: 300,
      points_against: 280,
      faab_remaining: null,
      waiver_position: null,
      is_user_team: false,
    },
    points,
    projected_points: 110,
    starters: [slot({ slot: "QB", player: player({ name: playerName, position: "QB" }), points: playerPoints, stat_line: `${playerPoints} pts` })],
  };
}

describe("MatchupSlate", () => {
  it("lists the other games and opens their starters", async () => {
    const user = userEvent.setup();
    render(<MatchupSlate games={[game("Gridiron Gurus", "Rivals", true), game("Touchdown Titans", "Blitz Brigade")]} week={4} />);
    expect(screen.queryByText("Gridiron Gurus")).not.toBeInTheDocument();
    expect(screen.getByText("Touchdown Titans")).toBeInTheDocument();
    expect(screen.getByText("Blitz Brigade")).toBeInTheDocument();
    expect(screen.getByText("88.0")).toBeInTheDocument();
    expect(screen.getByText("91.0")).toBeInTheDocument();
    expect(screen.getByText("Upcoming")).toBeInTheDocument();
    expect(screen.getAllByText(/Proj 110.0/).length).toBeGreaterThan(0);
    expect(screen.queryByText("Touchdown Titans QB")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Starters" }));
    expect(screen.getByText("Touchdown Titans QB")).toBeInTheDocument();
    expect(screen.getByText("Blitz Brigade QB")).toBeInTheDocument();
  });
});

describe("LeagueGames", () => {
  it("lists every league game, including yours", () => {
    render(<LeagueGames games={[game("Gridiron Gurus", "Rivals", true), game("Touchdown Titans", "Blitz Brigade")]} week={4} />);
    expect(screen.getByText("Gridiron Gurus")).toBeInTheDocument();
    expect(screen.getByText("Touchdown Titans")).toBeInTheDocument();
    expect(screen.getByTestId("league-games").querySelector('[data-yours="true"]')).toHaveTextContent("Gridiron Gurus");
    expect(screen.getAllByTestId("league-game")).toHaveLength(2);
    const yours = screen.getByTestId("league-games").querySelector('[data-yours="true"]');
    expect(yours).toHaveTextContent("10.0");
    expect(yours).toHaveTextContent("12.0");
    expect(screen.getAllByText("Upcoming")).toHaveLength(2);
    expect(screen.getAllByTestId("score-row").length).toBeGreaterThanOrEqual(4);
  });

  it("shows Final when every NFL game is over", () => {
    render(
      <LeagueGames
        games={[{ ...game("Gridiron Gurus", "Rivals", true), status: "in_progress" }]}
        week={4}
        nfl={[
          {
            away: "ATL",
            home: "GB",
            away_score: 17,
            home_score: 7,
            state: "post",
            detail: "Final",
            summary: null,
            broadcast: "FOX",
          },
        ]}
      />,
    );
    expect(screen.getByText("Final")).toBeInTheDocument();
    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });

  it("shows Final when every starter has played, even if another NFL game is live", () => {
    const played = game("Gridiron Gurus", "Rivals", true);
    for (const side of [played.team, played.opponent!]) {
      side.starters = side.starters.map((entry) => ({
        ...entry,
        game: {
          projected_points: 14,
          points: entry.points,
          stat_line: null,
          opponent: "BUF",
          home: true,
          away: "BUF",
          home_team: "KC",
          away_score: 10,
          home_score: 17,
          state: "post" as const,
          clock: "Final",
        },
      }));
    }
    render(
      <LeagueGames
        games={[{ ...played, status: "in_progress" }]}
        week={4}
        nfl={[
          {
            away: "SEA",
            home: "LAR",
            away_score: 7,
            home_score: 3,
            state: "in",
            detail: "8:22 - 2nd",
            summary: null,
            broadcast: "NBC",
          },
        ]}
      />,
    );
    expect(screen.getByText("Final")).toBeInTheDocument();
    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });

  it("stays Live while a starter's game is still going", () => {
    const playing = game("Gridiron Gurus", "Rivals", true);
    playing.team.starters = playing.team.starters.map((entry) => ({
      ...entry,
      game: {
        projected_points: 14,
        points: entry.points,
        stat_line: null,
        opponent: "BUF",
        home: true,
        away: "BUF",
        home_team: "KC",
        away_score: 10,
        home_score: 7,
        state: "in" as const,
        clock: "8:22 - 2nd",
      },
    }));
    render(<LeagueGames games={[{ ...playing, status: "in_progress" }]} week={4} />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("opens a game to compare starters", async () => {
    const user = userEvent.setup();
    render(<LeagueGames games={[game("Gridiron Gurus", "Rivals", true), game("Touchdown Titans", "Blitz Brigade")]} week={4} />);
    await user.click(screen.getByText("Touchdown Titans"));
    expect(screen.getByTestId("game-score")).toHaveTextContent("88.0");
    expect(screen.getByTestId("game-score")).toHaveTextContent("91.0");
    expect(screen.getByText("Playing well")).toBeInTheDocument();
    expect(screen.getByTestId("hot-list")).toHaveTextContent("Blitz Brigade QB");
    expect(screen.getByTestId("hot-list")).toHaveTextContent("28.0");
    expect(screen.getAllByText("Touchdown Titans QB").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Blitz Brigade QB").length).toBeGreaterThan(0);
  });
});
