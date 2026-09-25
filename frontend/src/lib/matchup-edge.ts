import type { RosterSlot } from "./types";

export interface SlotScore {
  value: number | null;
  live: boolean;
}

/** Projection until that player's game starts, then the points they have scored. */
export function slotScore(slot: RosterSlot | null | undefined, week: number): SlotScore {
  if (!slot?.player) return { value: null, live: false };
  const game = slot.player.schedule.find((item) => item.week === week);
  if (game?.state === "pre") return { value: slot.player.projected_points ?? null, live: false };
  if (game?.state === "in" || game?.state === "post") return { value: slot.points ?? 0, live: true };
  if (slot.points != null && slot.points > 0) return { value: slot.points, live: true };
  return { value: slot.player.projected_points ?? null, live: false };
}

export function scoreEdge(yours: SlotScore, theirs: SlotScore): number | null {
  if (yours.value == null || theirs.value == null) return null;
  return Math.round((yours.value - theirs.value) * 10) / 10;
}
