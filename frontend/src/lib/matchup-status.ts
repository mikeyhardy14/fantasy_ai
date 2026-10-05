import type { NflGame, RosterSlot } from "@/lib/types";

export function playerHasPlayed(slot: RosterSlot): boolean {
  const person = slot.player;
  if (!person) return true;
  if (person.on_bye || slot.flags.includes("BYE")) return true;
  if (slot.game?.state === "post") return true;
  return !person.nfl_team;
}

/** Every starter who is actually rostered has finished their week. */
export function lineupHasPlayed(starters: RosterSlot[]): boolean {
  const rostered = starters.filter((slot) => slot.player);
  return rostered.length > 0 && rostered.every(playerHasPlayed);
}

export function slateOver(nfl: NflGame[] | undefined): boolean {
  if (!nfl || nfl.length === 0) return false;
  return nfl.every((game) => game.state === "post");
}

export function fantasyLabel(status: string, starters: RosterSlot[], nfl?: NflGame[]): string {
  if (status === "bye") return "Bye";
  if (status === "final" || slateOver(nfl) || lineupHasPlayed(starters)) return "Final";
  if (status === "in_progress") return "Live";
  return "Upcoming";
}
