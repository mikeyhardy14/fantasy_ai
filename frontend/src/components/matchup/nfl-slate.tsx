import { HotList, playersInNflGame } from "@/components/matchup/hot-list";
import { ScoreBox, ScoreBoxSide, ScoreMark } from "@/components/matchup/score-box";
import { Pop } from "@/components/ui/pop";
import type { NflGame, RosterSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useState } from "react";

const gamesByTeam = new WeakMap<NflGame[], Map<string, NflGame>>();

const ESPN_TEAM: Record<string, string> = { WAS: "wsh", WSH: "wsh", JAC: "jax" };

export function teamLogoUrl(abbr: string): string {
  const code = ESPN_TEAM[abbr.toUpperCase()] ?? abbr.toLowerCase();
  return `https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/${code}.png&w=48&h=48`;
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

function postedScore(value: number | null, state: string | null): string {
  if (state === "pre" || value == null) return "—";
  return String(value);
}

function leading(game: NflGame, side: "away" | "home"): boolean {
  if (game.state === "pre" || game.away_score == null || game.home_score == null) return false;
  if (game.away_score === game.home_score) return false;
  return side === "away" ? game.away_score > game.home_score : game.home_score > game.away_score;
}

function nflStatus(game: NflGame): string {
  if (game.state === "in") return "Live";
  if (game.state === "post") return "Final";
  return "Upcoming";
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
      <ul className={cn("grid gap-1.5 p-2", compact ? "grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" : "sm:grid-cols-2 xl:grid-cols-3")}>
        {games.map((game, index) => {
          const live = game.state === "in";
          return (
            <li key={`${game.away}-${game.home}`}>
              <ScoreBox
                data-testid="nfl-game"
                data-live={live ? "true" : "false"}
                live={live}
                compact={compact}
                status={nflStatus(game)}
                clock={game.detail}
                footer={
                  <>
                    <StreamLine game={game} />
                    {compact ? null : game.summary ? <p className="text-sm text-slate-200">{game.summary}</p> : null}
                  </>
                }
                onClick={() => setOpen(game)}
              >
                <ScoreBoxSide
                  mark={<TeamMark abbr={game.away} ring={live && game.possession === game.away} priority={index < 2} />}
                  name={game.away}
                  score={postedScore(game.away_score, game.state)}
                  ahead={leading(game, "away")}
                />
                <ScoreBoxSide
                  mark={<TeamMark abbr={game.home} ring={live && game.possession === game.home} priority={index < 2} />}
                  name={game.home}
                  score={postedScore(game.home_score, game.state)}
                  ahead={leading(game, "home")}
                />
              </ScoreBox>
            </li>
          );
        })}
      </ul>
      {open ? (
        <Pop title={gameLine(open)} onClose={() => setOpen(null)}>
          <div className="space-y-2 border-b border-white/10 px-4 py-3 text-sm" data-testid="nfl-game-detail">
            <span className="sr-only">{gameLine(open)}</span>
            <ScoreBoxSide
              mark={<TeamMark abbr={open.away} size="md" ring={open.state === "in" && open.possession === open.away} />}
              name={open.away}
              score={postedScore(open.away_score, open.state)}
              ahead={leading(open, "away")}
            />
            <ScoreBoxSide
              mark={<TeamMark abbr={open.home} size="md" ring={open.state === "in" && open.possession === open.home} />}
              name={open.home}
              score={postedScore(open.home_score, open.state)}
              ahead={leading(open, "home")}
            />
            <p className="text-xs text-slate-400">
              {nflStatus(open)}
              {open.detail ? ` · ${open.detail}` : ""}
            </p>
            <StreamLine game={open} />
            {open.summary ? <p className="pt-1 text-sm text-slate-200">{open.summary}</p> : null}
          </div>
          <p className="px-4 pt-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">In this league</p>
          <HotList slots={playersInNflGame(open, slots)} />
        </Pop>
      ) : null}
    </>
  );
}

function TeamMark({ abbr, ring, size, priority }: { abbr: string; ring?: boolean; size?: "sm" | "md"; priority?: boolean }) {
  return <ScoreMark src={teamLogoUrl(abbr)} label={abbr} alt={`${abbr} logo`} ring={ring} size={size} priority={priority} />;
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
  return <img src={mark.src} alt={`${mark.label} logo`} width={44} height={16} loading="lazy" decoding="async" className="h-4 w-auto max-w-[2.75rem] shrink-0 object-contain" onError={() => setFailed(true)} />;
}
