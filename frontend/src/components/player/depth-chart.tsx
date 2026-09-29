import { gameScore, PlayerFace, PlayStatus, playPhase, playRowClass } from "@/components/player/player-face";
import { PlayerName } from "@/components/player/player-sheet";
import type { RankingRow } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";

function teamGame(rows: RankingRow[]) {
  return rows.find((row) => row.game && (row.game.away || row.game.home_team || row.game.opponent))?.game ?? null;
}

export function DepthChart({ rows, team }: { rows: RankingRow[]; team: string }) {
  const groups = ["QB", "RB", "WR", "TE", "K", "DEF"]
    .map((position) => ({
      position,
      players: rows
        .filter((row) => row.position === position)
        .sort((left, right) => (right.projected_points ?? -1) - (left.projected_points ?? -1) || left.name.localeCompare(right.name)),
    }))
    .filter((group) => group.players.length);
  const game = teamGame(rows);
  const matchup = game?.away && game.home_team ? `${game.away} at ${game.home_team}` : game?.opponent ? `${team} ${game.home === false ? "at" : "vs"} ${game.opponent}` : null;
  const score = game ? gameScore(game) : null;
  if (!groups.length) return <p className="text-sm text-slate-500">No {team} players in this list.</p>;
  return (
    <div data-testid="depth-chart" className="space-y-4">
      <div data-testid="team-game" className="border border-surface-border bg-surface px-4 py-3">
        {matchup || score ? (
          <>
            <p className="text-sm font-medium tabular-nums text-slate-100">{score ?? matchup}</p>
            {game?.clock ? <p className="mt-1 text-[11px] text-slate-400">{game.clock}</p> : null}
            {game?.state === "in" && game.possession ? <p className="mt-1 text-[11px] font-medium text-emerald-200">Ball: {game.possession}</p> : null}
          </>
        ) : (
          <p className="text-sm text-slate-400">{team} is on bye this week.</p>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {groups.map((group) => (
          <div key={group.position}>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">{group.position}</p>
            <ul className="mt-1 space-y-1.5">
              {group.players.map((row, index) => {
                const phase = playPhase(row.game, row.position, row.nfl_team);
                return (
                  <li key={row.player_id} className={cn("flex flex-wrap items-center gap-1.5 rounded-md px-1 py-0.5 text-sm text-slate-200", playRowClass(phase))}>
                    <span className="text-slate-500">{index + 1}.</span>
                    <PlayerFace url={row.headshot_url} name={row.name} size="xs" />
                    <PlayerName id={row.player_id} name={row.name} className="font-medium text-slate-100" />
                    <PlayStatus phase={phase} />
                    <span className="text-slate-400">
                      {row.injury_status ? ` · ${row.injury_status}` : ""}
                      {` · Proj ${formatPoints(row.projected_points)}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
