import type { Recommendation } from "./types";

const PREFIX = "omaha.dismissed-recs.";

export function recKey(rec: Recommendation): string {
  return `${rec.type}:${rec.title}`;
}

export function readDismissed(leagueId: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(`${PREFIX}${leagueId}`);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function writeDismissed(leagueId: string, keys: string[]): void {
  window.localStorage.setItem(`${PREFIX}${leagueId}`, JSON.stringify(keys));
}

export function recAction(rec: Recommendation): "do" | "add" | "drop" | "open" | null {
  if (rec.type === "START_SIT" && rec.players[0]) return "do";
  if ((rec.type === "WAIVER_TARGET" || rec.type === "ADD_PLAYER") && rec.players[0]) return "add";
  if (rec.type === "DROP_PLAYER" && rec.players[0]) return "drop";
  if (rec.type === "TRADE_TARGET" || rec.type === "INJURY_ALERT" || rec.type === "BYE_WEEK" || rec.type === "ROSTER_WEAKNESS") return "open";
  return rec.players[0] ? "do" : null;
}

export function recActionLabel(rec: Recommendation): string {
  const action = recAction(rec);
  if (action === "add") return "Add";
  if (action === "drop") return "Drop";
  if (action === "open") return rec.type === "TRADE_TARGET" ? "Trade" : rec.type === "ROSTER_WEAKNESS" ? "Players" : "Lineup";
  return "Do";
}
