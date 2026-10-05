import { fantasyLabel, lineupHasPlayed } from "@/lib/matchup-status";
import { player, slot } from "./fixtures";

const done = slot({
  player: player({ nfl_team: "KC" }),
  game: {
    projected_points: 12,
    points: 14,
    stat_line: null,
    opponent: "BUF",
    home: true,
    away: "BUF",
    home_team: "KC",
    away_score: 10,
    home_score: 17,
    state: "post",
    clock: "Final",
  },
});

describe("lineupHasPlayed", () => {
  it("is true once every rostered starter's game is final", () => {
    expect(lineupHasPlayed([done, slot({ player: null })])).toBe(true);
  });

  it("is false while a starter is still in their game", () => {
    const live = slot({
      player: player({ nfl_team: "DAL" }),
      game: { ...done.game!, state: "in", home_team: "DAL" },
    });
    expect(lineupHasPlayed([done, live])).toBe(false);
  });

  it("treats a bye as already played", () => {
    expect(lineupHasPlayed([done, slot({ player: player({ on_bye: true, nfl_team: "GB" }), flags: ["BYE"] })])).toBe(true);
  });
});

describe("fantasyLabel", () => {
  it("says Final instead of Live when the lineup is done", () => {
    expect(fantasyLabel("in_progress", [done], [{ away: "SEA", home: "LAR", away_score: 3, home_score: 0, state: "in", detail: "1st", summary: null, broadcast: null }])).toBe("Final");
  });
});
