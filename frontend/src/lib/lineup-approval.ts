import type { LineupAction } from "@/lib/types";

const KEY = "omaha.lineup-auto-approve";

export function readLineupAutoApprove(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(KEY) === "1";
}

export function writeLineupAutoApprove(on: boolean): void {
  window.localStorage.setItem(KEY, on ? "1" : "0");
}

/** One decided start-over per slot. A menu of replacements for the same slot stays a choice. */
export function movesToApply(actions: LineupAction[]): LineupAction[] {
  const groups = new Map<number, LineupAction[]>();
  for (const action of actions) {
    if (!action.replaces) continue;
    const list = groups.get(action.slot_index) ?? [];
    list.push(action);
    groups.set(action.slot_index, list);
  }
  return [...groups.values()].filter((list) => list.length === 1).map((list) => list[0]);
}

export function moveSummary(action: LineupAction): string {
  if (action.summary) return action.summary;
  if (action.replaces) return `Start ${action.player_name} over ${action.replaces} at ${action.slot}.`;
  return action.label;
}
