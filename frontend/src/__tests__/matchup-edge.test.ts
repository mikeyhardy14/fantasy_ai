import { scoreEdge, slotScore } from "@/lib/matchup-edge";
import type { RosterSlot } from "@/lib/types";
import { player, slot } from "./fixtures";

function lined(points: number | null, projected: number | null, state: "pre" | "in" | "post" | null): RosterSlot {
  return slot({
    points,
    player: player({
      projected_points: projected,
      schedule: [{ week: 3, opponent: "BUF", home: true, spread: null, total: null, implied_points: null, state }],
    }),
  });
}

describe("matchup edge", () => {
  it("uses the projection until the game starts", () => {
    const score = slotScore(lined(0, 18.4, "pre"), 3);
    expect(score).toEqual({ value: 18.4, live: false });
  });

  it("uses current points once the game is live or finished", () => {
    expect(slotScore(lined(9.2, 18.4, "in"), 3)).toEqual({ value: 9.2, live: true });
    expect(slotScore(lined(21, 18.4, "post"), 3)).toEqual({ value: 21, live: true });
    expect(slotScore(lined(0, 18.4, "in"), 3)).toEqual({ value: 0, live: true });
  });

  it("uses points already posted before the schedule state arrives", () => {
    expect(slotScore(lined(9.2, 18.4, null), 3)).toEqual({ value: 9.2, live: true });
  });

  it("measures your edge against the other starter", () => {
    const yours = slotScore(lined(null, 16, "pre"), 3);
    const theirs = slotScore(lined(11, 20, "in"), 3);
    expect(scoreEdge(yours, theirs)).toBe(5);
  });
});
