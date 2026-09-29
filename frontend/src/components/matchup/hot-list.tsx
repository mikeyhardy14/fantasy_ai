import { PlayerFace } from "@/components/player/player-face";
import { PlayerName } from "@/components/player/player-sheet";
import type { LeagueMatchup, NflGame, RosterSlot } from "@/lib/types";
import { formatPoints } from "@/lib/utils";

export function slotsFromMatchups(games: LeagueMatchup[]): RosterSlot[] {
  return games.flatMap((game) => [...game.team.starters, ...(game.opponent?.starters ?? [])]);
}

export function hotPlayers(slots: RosterSlot[], limit = 6): RosterSlot[] {
  const live = slots.filter((slot) => slot.player && ((slot.points ?? 0) > 0 || slot.stat_line || slot.game?.stat_line));
  const pool = live.length ? live : slots.filter((slot) => slot.player);
  return [...pool].sort((left, right) => scoreOf(right) - scoreOf(left)).slice(0, limit);
}

export function playersInNflGame(game: NflGame, slots: RosterSlot[], limit = 8): RosterSlot[] {
  const clubs = new Set([game.away, game.home]);
  const seen = new Set<string>();
  const hits: RosterSlot[] = [];
  for (const slot of slots) {
    const player = slot.player;
    if (!player || seen.has(player.id) || !player.nfl_team || !clubs.has(player.nfl_team)) continue;
    seen.add(player.id);
    hits.push(slot);
  }
  return hotPlayers(hits, limit);
}

function scoreOf(slot: RosterSlot): number {
  return slot.points ?? slot.player?.projected_points ?? -1;
}

export function HotList({ slots }: { slots: RosterSlot[] }) {
  if (!slots.length) return <p className="px-4 py-3 text-xs text-slate-500">No player stats yet.</p>;
  return (
    <ul data-testid="hot-list">
      {slots.map((slot) => {
        const player = slot.player!;
        const line = slot.stat_line || slot.game?.stat_line;
        return (
          <li key={player.id} className="flex items-center gap-2 px-4 py-1.5" data-testid="hot-player">
            <PlayerFace url={player.headshot_url} name={player.name} size="xs" />
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline gap-1.5">
                <PlayerName id={player.id} name={player.name} className="truncate text-xs font-medium text-slate-100" />
                <span className="shrink-0 text-[10px] text-slate-500">{player.nfl_team ?? player.position}</span>
              </span>
              {line ? <span className="block truncate text-[11px] text-slate-400">{line}</span> : null}
            </span>
            <span className="shrink-0 tabular-nums text-sm text-slate-100">{formatPoints(slot.points ?? player.projected_points)}</span>
          </li>
        );
      })}
    </ul>
  );
}
