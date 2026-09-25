import type { NflGame } from "@/lib/types";
import { cn } from "@/lib/utils";

export function gameForTeam(team: string | null | undefined, games: NflGame[]): NflGame | undefined {
  if (!team) return undefined;
  return games.find((game) => game.home === team || game.away === team);
}

export function gameLine(game: NflGame): string {
  if (game.state === "pre" || game.away_score == null || game.home_score == null) {
    return `${game.away} at ${game.home}`;
  }
  return `${game.away} ${game.away_score}, ${game.home} ${game.home_score}`;
}

export function NflSlate({ games }: { games: NflGame[] }) {
  if (!games.length) return <p className="px-5 py-6 text-sm text-slate-500">No NFL games posted for this week.</p>;
  return (
    <ul className="divide-y divide-surface-border/60">
      {games.map((game) => {
        const live = game.state === "in";
        return (
        <li
          key={`${game.away}-${game.home}`}
          className={cn("px-5 py-3", live && "border-l-2 border-l-red-400 bg-red-500/10")}
          data-testid="nfl-game"
          data-live={live ? "true" : "false"}
        >
          <div className="flex items-baseline justify-between gap-3">
            <p className={cn("text-sm font-medium tabular-nums", live ? "text-slate-100" : "text-slate-300")}>
              {gameLine(game)}
            </p>
            <p className={cn("shrink-0 text-[11px]", live ? "font-semibold uppercase tracking-wide text-red-300" : "text-slate-500")}>
              {live ? "Live" : game.detail ?? "—"}
              {game.broadcast ? ` · ${game.broadcast}` : ""}
            </p>
          </div>
          {live && game.detail ? <p className="mt-1 text-[11px] text-slate-500">{game.detail}</p> : null}
          {game.summary ? <p className="mt-1 text-sm text-slate-200">{game.summary}</p> : null}
        </li>
        );
      })}
    </ul>
  );
}
