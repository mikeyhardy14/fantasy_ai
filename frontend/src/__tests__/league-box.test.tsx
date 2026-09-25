import { LeagueBox } from "@/components/league-box";
import { leagueInitials, leagueLocation } from "@/lib/league-location";
import type { League, Matchup, Team } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { player, slot } from "./fixtures";

vi.mock("next/link", () => ({
  default: ({ href, children, onClick }: { href: string; children: ReactNode; onClick?: () => void }) => (
    <a
      href={href}
      onClick={(event) => {
        event.preventDefault();
        onClick?.();
      }}
    >
      {children}
    </a>
  ),
}));

function league(overrides: Partial<League> = {}): League {
  return {
    id: "league-1",
    provider: "sleeper",
    external_league_id: "999",
    name: "Gridiron Gurus",
    season: 2026,
    team_count: 12,
    current_week: 3,
    status: "in_season",
    avatar: "https://sleepercdn.com/avatars/thumbs/abc",
    scoring_type: "PPR",
    last_synced_at: null,
    sync_status: "success",
    sync_error: null,
    user_team_id: "team-1",
    user_team_name: "Mike's Marauders",
    ...overrides,
  };
}

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
  week: 3,
  starters: [slot({ slot: "QB", player: player({ name: "Quinn Arrow", position: "QB", nfl_team: "KC" }), points: 18.4 })],
  bench: [],
  reserve: [],
  lineup_slots: ["QB"],
  lineup_issues: ["TE slot is empty."],
  projected_points: 110.2,
  projection_coverage: "partial",
};

const matchup: Matchup = {
  week: 3,
  is_bye: false,
  status: "in_progress",
  user: {
    team: team.team,
    points: 88.1,
    projected_points: 110.2,
    starters: team.starters,
  },
  opponent: {
    team: { ...team.team, id: "team-2", name: "Rivals", is_user_team: false, record: "1-2" },
    points: 91.4,
    projected_points: 105,
    starters: [],
  },
};

describe("league location", () => {
  it("builds a Sleeper league link and a platform label", () => {
    const location = leagueLocation(league());
    expect(location.label).toBe("Sleeper");
    expect(location.hostedOn).toBe("sleeper.com");
    expect(location.href).toBe("https://sleeper.com/leagues/999");
  });

  it("builds Yahoo, ESPN, and NFL links", () => {
    expect(leagueLocation(league({ provider: "yahoo", external_league_id: "449.l.12345" })).href).toBe(
      "https://football.fantasysports.yahoo.com/f1/449.l.12345",
    );
    expect(leagueLocation(league({ provider: "espn", external_league_id: "555", season: 2026 })).href).toBe(
      "https://fantasy.espn.com/football/league?leagueId=555&seasonId=2026",
    );
    expect(leagueLocation(league({ provider: "nfl", external_league_id: "42" })).href).toBe("https://fantasy.nfl.com/league/42");
  });

  it("keeps demo leagues inside the app and rejects unsafe ids", () => {
    expect(leagueLocation(league({ provider: "demo", external_league_id: "demo-league" })).href).toBeNull();
    expect(leagueLocation(league({ external_league_id: "https://evil.example" })).href).toBeNull();
    expect(leagueInitials("Gridiron Gurus")).toBe("GG");
  });
});

describe("LeagueBox", () => {
  it("shows the league icon, where it is hosted, and links", async () => {
    const onSelect = vi.fn();
    render(<LeagueBox league={league()} team={team} matchup={matchup} loading={false} error={null} onSelect={onSelect} />);

    expect(screen.getByText("Gridiron Gurus")).toBeInTheDocument();
    expect(screen.getByText(/On sleeper.com/)).toBeInTheDocument();
    expect(screen.getByTestId("platform-icon")).toHaveTextContent("S");
    expect(screen.getByTestId("league-avatar")).toHaveAttribute("src", "https://sleepercdn.com/avatars/thumbs/abc");
    expect(screen.getByRole("link", { name: /Open on Sleeper/ })).toHaveAttribute("href", "https://sleeper.com/leagues/999");
    expect(screen.getByText("Quinn Arrow")).toBeInTheDocument();
    expect(screen.getByText("proj")).toBeInTheDocument();
    expect(screen.getByText("14.2")).toBeInTheDocument();
    expect(screen.queryByText("total")).toBeNull();
    expect(screen.getByRole("list")).not.toHaveClass("mt-auto");
    expect(screen.getByText("1 lineup issue")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: "Roster" }));
    expect(onSelect).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Roster" })).toHaveAttribute("href", "/team");
  });

  it("sets a lineup from the slot box when Sleeper writes are on", async () => {
    const onMove = vi.fn();
    const editable = {
      ...team,
      starters: [slot({ slot: "QB", slot_index: 0, player: player({ id: "qb-1", name: "Quinn Arrow", position: "QB", fantasy_positions: ["QB"] }), points: 18.4 })],
      bench: [slot({ slot: "BN", slot_index: null, is_starter: false, player: player({ id: "rb-1", name: "Backup Back", position: "RB", fantasy_positions: ["RB"] }), points: null })],
      lineup_slots: ["QB", "RB"],
    };
    render(
      <LeagueBox
        league={league()}
        team={editable}
        matchup={matchup}
        loading={false}
        error={null}
        onSelect={vi.fn()}
        canEdit
        irCapacity={1}
        onMove={onMove}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Move Backup Back" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Start at RB" }));
    expect(onMove).toHaveBeenCalledWith({ playerId: "rb-1", destination: "starter", slotIndex: 1 });
  });

  it("uses initials when a league has no icon", () => {
    render(
      <LeagueBox
        league={league({ avatar: null, provider: "demo", external_league_id: "demo-league", name: "Sunday Sample" })}
        loading={false}
        error={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByTestId("league-avatar")).toHaveTextContent("SS");
    expect(screen.getByText("Hosted in this app")).toBeInTheDocument();
    expect(screen.getByTestId("platform-icon")).toHaveTextContent("D");
  });
});
