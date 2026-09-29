import { HotList, playersInNflGame } from "@/components/matchup/hot-list";
import { Pop } from "@/components/ui/pop";
import type { NflGame, RosterSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useState } from "react";

const gamesByTeam = new WeakMap<NflGame[], Map<string, NflGame>>();

const ESPN_TEAM: Record<string, string> = { WAS: "wsh", WSH: "wsh", JAC: "jax" };

export function teamLogoUrl(abbr: string): string {
  const code = ESPN_TEAM[abbr.toUpperCase()] ?? abbr.toLowerCase();
  return `https://a.espncdn.com/i/teamlogos/nfl/500/${code}.png`;
}

const NETWORK_MARKS: Record<string, { src: string; label: string }> = {
  "prime video": { src: "https://cdn.simpleicons.org/amazonprime/00A8E1", label: "Prime Video" },
  "amazon prime video": { src: "https://cdn.simpleicons.org/amazonprime/00A8E1", label: "Prime Video" },
  amazon: { src: "https://cdn.simpleicons.org/amazonprime/00A8E1", label: "Prime Video" },
  fox: { src: "https://cdn.simpleicons.org/fox/ffffff", label: "FOX" },
  nbc: { src: "https://cdn.simpleicons.org/nbc/ffffff", label: "NBC" },
  cbs: { src: "https://cdn.simpleicons.org/cbs/003CA6", label: "CBS" },
  espn: { src: "https://cdn.simpleicons.org/espn/D00", label: "ESPN" },
  espn2: { src: "https://cdn.simpleicons.org/espn/D00", label: "ESPN2" },
  "espn+": { src: "https://cdn.simpleicons.org/espn/D00", label: "ESPN+" },
  abc: { src: "https://cdn.simpleicons.org/americanbroadcastingcompany/ffffff", label: "ABC" },
  peacock: { src: "https://cdn.simpleicons.org/peacock/000000", label: "Peacock" },
  youtube: { src: "https://cdn.simpleicons.org/youtube/FF0000", label: "YouTube" },
  "youtube tv": { src: "https://cdn.simpleicons.org/youtubetv/FF0000", label: "YouTube TV" },
  "apple tv": { src: "https://cdn.simpleicons.org/appletv/ffffff", label: "Apple TV" },
  "apple tv+": { src: "https://cdn.simpleicons.org/appletv/ffffff", label: "Apple TV+" },
  "nfl network": { src: "https://cdn.simpleicons.org/nfl/013369", label: "NFL Network" },
  nfln: { src: "https://cdn.simpleicons.org/nfl/013369", label: "NFL Network" },
  "nfl+": { src: "https://cdn.simpleicons.org/nfl/013369", label: "NFL+" },
};

function networkKey(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9+]+/g, " ").trim();
}

export function networkMark(name: string): { src: string; label: string } | null {
  const key = networkKey(name);
  if (NETWORK_MARKS[key]) return NETWORK_MARKS[key];
  if (key.includes("prime")) return NETWORK_MARKS["prime video"];
  if (key.startsWith("espn")) return NETWORK_MARKS.espn;
  if (key.includes("youtube")) return NETWORK_MARKS.youtube;
  if (key.includes("apple")) return NETWORK_MARKS["apple tv"];
  if (key.includes("peacock")) return NETWORK_MARKS.peacock;
  if (key.includes("nfl")) return NETWORK_MARKS["nfl network"];
  return null;
}

export function streamWhere(game: NflGame): string | null {
  const market = (game.broadcast_market ?? "").toLowerCase();
  const where =
    market === "national" ? "National" : market === "home" ? `${game.home} market` : market === "away" ? `${game.away} market` : null;
  const parts = [where, game.venue].filter((part): part is string => Boolean(part));
  return parts.length ? parts.join(" · ") : null;
}

function indexGames(games: NflGame[]): Map<string, NflGame> {
  const cached = gamesByTeam.get(games);
  if (cached) return cached;
  const index = new Map<string, NflGame>();
  for (const game of games) {
    if (game.away && !index.has(game.away)) index.set(game.away, game);
    if (game.home && !index.has(game.home)) index.set(game.home, game);
  }
  gamesByTeam.set(games, index);
  return index;
}

export function gameForTeam(team: string | null | undefined, games: NflGame[]): NflGame | undefined {
  if (!team) return undefined;
  return indexGames(games).get(team);
}

export function gameLine(game: NflGame): string {
  if (game.state === "pre" || game.away_score == null || game.home_score == null) {
    return `${game.away} at ${game.home}`;
  }
  return `${game.away} ${game.away_score}, ${game.home} ${game.home_score}`;
}

export function NflSlate({
  games,
  compact = false,
  slots = [],
}: {
  games: NflGame[];
  compact?: boolean;
  slots?: RosterSlot[];
}) {
  const [open, setOpen] = useState<NflGame | null>(null);
  if (!games.length) return <p className="px-3 py-4 text-xs text-slate-500">No NFL games this week.</p>;
  return (
    <>
      <ul className="divide-y divide-surface-border/60">
        {games.map((game) => {
          const live = game.state === "in";
          return (
            <li key={`${game.away}-${game.home}`}>
              <button
                type="button"
                data-testid="nfl-game"
                data-live={live ? "true" : "false"}
                className={cn(
                  "w-full text-left",
                  compact ? "px-3 py-2" : "px-5 py-3",
                  live && "border-l-2 border-l-red-400 bg-red-500/10",
                )}
                onClick={() => setOpen(game)}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <TeamMark team={game.away} ball={live && game.possession === game.away} />
                    <span className={cn("text-sm font-medium tabular-nums", live ? "text-slate-100" : "text-slate-300")}>
                      {gameLine(game)}
                    </span>
                    <TeamMark team={game.home} ball={live && game.possession === game.home} />
                  </div>
                  <p className={cn("shrink-0 text-[11px]", live ? "font-semibold uppercase tracking-wide text-red-300" : "text-slate-500")}>
                    {live ? "Live" : game.detail ?? "—"}
                  </p>
                </div>
                <StreamLine game={game} className="mt-1" />
                {compact ? null : (
                  <>
                    {live && game.possession ? <p className="mt-1 text-[11px] font-medium text-emerald-200">Ball: {game.possession}</p> : null}
                    {live && game.detail ? <p className="mt-1 text-[11px] text-slate-500">{game.detail}</p> : null}
                    {game.summary ? <p className="mt-1 text-sm text-slate-200">{game.summary}</p> : null}
                  </>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {open ? (
        <Pop title={gameLine(open)} onClose={() => setOpen(null)}>
          <div className="space-y-2 border-b border-white/10 px-4 py-3 text-sm" data-testid="nfl-game-detail">
            <div className="flex items-center gap-3">
              <TeamMark team={open.away} size="md" ball={open.state === "in" && open.possession === open.away} />
              <p className="font-serif text-2xl tabular-nums text-slate-100">{gameLine(open)}</p>
              <TeamMark team={open.home} size="md" ball={open.state === "in" && open.possession === open.home} />
            </div>
            <p className="text-xs text-slate-400">
              {open.state === "in" ? "Live" : open.state === "post" ? "Final" : "Upcoming"}
              {open.detail ? ` · ${open.detail}` : ""}
            </p>
            <StreamLine game={open} />
            {open.possession ? <p className="text-xs font-medium text-emerald-200">Ball: {open.possession}</p> : null}
            {open.summary ? <p className="pt-1 text-sm text-slate-200">{open.summary}</p> : null}
          </div>
          <p className="px-4 pt-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">In this league</p>
          <HotList slots={playersInNflGame(open, slots)} />
        </Pop>
      ) : null}
    </>
  );
}

function TeamMark({ team, size = "sm", ball }: { team: string; size?: "sm" | "md"; ball?: boolean }) {
  const [failed, setFailed] = useState(false);
  const box = size === "md" ? "h-8 w-8" : "h-6 w-6";
  return (
    <span className={cn("relative inline-flex shrink-0", ball && "rounded-full ring-2 ring-emerald-300")}>
      {failed ? (
        <span className={cn("inline-flex items-center justify-center rounded-full bg-surface-overlay text-[9px] font-semibold text-slate-300", box)}>
          {team}
        </span>
      ) : (
        <img src={teamLogoUrl(team)} alt={`${team} logo`} className={cn("rounded-full bg-white object-contain", box)} onError={() => setFailed(true)} />
      )}
    </span>
  );
}

function StreamLine({ game, className }: { game: NflGame; className?: string }) {
  const where = streamWhere(game);
  if (!game.broadcast && !where) return null;
  return (
    <p className={cn("flex min-w-0 items-center gap-1.5 text-[11px] text-slate-400", className)}>
      {game.broadcast ? <NetworkMark name={game.broadcast} /> : null}
      <span className="min-w-0 truncate">{[game.broadcast, where].filter(Boolean).join(" · ")}</span>
    </p>
  );
}

function NetworkMark({ name }: { name: string }) {
  const [failed, setFailed] = useState(false);
  const mark = networkMark(name);
  if (!mark || failed) {
    return (
      <span className="inline-flex h-4 shrink-0 items-center rounded bg-white/10 px-1 text-[9px] font-semibold uppercase tracking-wide text-slate-200">
        {name}
      </span>
    );
  }
  return <img src={mark.src} alt={`${mark.label} logo`} className="h-4 w-auto max-w-[2.75rem] shrink-0 object-contain" onError={() => setFailed(true)} />;
}
