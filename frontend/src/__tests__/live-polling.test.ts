import { matchupLive, pollWhile, teamLive } from "@/lib/queries";
import type { GameLook, Matchup, Team } from "@/lib/types";
import { describe, expect, it } from "vitest";
import { slot } from "./fixtures";

function team(state: "pre" | "in" | "post" | null): Team {
  return {
    team: {
      id: "t",
      name: "Mine",
      owner_name: null,
      avatar: null,
      wins: 0,
      losses: 0,
      ties: 0,
      record: "0-0",
      points_for: 0,
      points_against: 0,
      faab_remaining: null,
      waiver_position: null,
      is_user_team: true,
    },
    week: 4,
    starters: [slot({ game: { state } as GameLook })],
    bench: [],
    reserve: [],
    lineup_slots: ["QB"],
    lineup_issues: [],
    projected_points: null,
    projection_coverage: "none",
  };
}

describe("game-aware polling", () => {
  it("polls fast only while a player on screen is in a game", () => {
    const interval = pollWhile(teamLive);
    expect(interval({ state: { data: team("in") } })).toBe(15_000);
    expect(interval({ state: { data: team("pre") } })).toBe(60_000);
    expect(interval({ state: { data: team("post") } })).toBe(60_000);
    expect(interval({ state: { data: undefined } })).toBe(60_000);
  });

  it("treats a matchup as live when any game this week is on", () => {
    const quiet = team("pre");
    const matchup: Matchup = {
      week: 4,
      is_bye: false,
      user: { team: quiet.team, points: 0, projected_points: null, starters: quiet.starters },
      opponent: null,
      status: "upcoming",
      games: [{ away: "SF", home: "SEA", away_score: 7, home_score: 3, state: "in", detail: null, summary: null, broadcast: null }],
    };
    expect(matchupLive(matchup)).toBe(true);
    expect(matchupLive({ ...matchup, games: [] })).toBe(false);
  });
});
