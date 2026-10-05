import { boardWeek } from "@/lib/week";

const done = [{ state: "post" as const }, { state: "post" as const }];
const live = [{ state: "post" as const }, { state: "in" as const }];

describe("boardWeek", () => {
  it("moves to the next week on Tuesday after every NFL game is final", () => {
    expect(boardWeek(4, done, new Date("2026-09-29T15:00:00Z"))).toBe(5);
  });

  it("stays on this week through Monday night", () => {
    expect(boardWeek(4, done, new Date("2026-09-28T20:00:00Z"))).toBe(4);
  });

  it("stays when a game is still in progress", () => {
    expect(boardWeek(4, live, new Date("2026-09-29T15:00:00Z"))).toBe(4);
  });
});
