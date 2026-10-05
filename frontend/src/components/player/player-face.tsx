"use client";

import { safeImageUrl } from "@/lib/league-location";
import type { GameLook, Player, ScheduleGame } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useState } from "react";

export function gameScore(game: GameLook): string | null {
  if (game.state === "pre" || game.away_score == null || game.home_score == null || !game.away || !game.home_team) return null;
  return `${game.away} ${game.away_score}, ${game.home_team} ${game.home_score}`;
}

const OFFENSE = new Set(["QB", "RB", "WR", "TE", "FLEX", "K", "SUPER_FLEX"]);

export type PlayPhase = "yet" | "live" | "field" | "done";

export function playPhase(
  game: { state?: string | null; possession?: string | null } | null | undefined,
  position?: string | null,
  nflTeam?: string | null,
): PlayPhase | null {
  if (game?.state === "pre") return "yet";
  if (game?.state === "post") return "done";
  if (game?.state !== "in") return null;
  const ball = game.possession?.toUpperCase();
  const team = nflTeam?.toUpperCase();
  if (!ball || !team) return "live";
  const ours = ball === team;
  const offense = !position || OFFENSE.has(position);
  return (offense ? ours : !ours) ? "field" : "live";
}

export function playRowClass(phase: PlayPhase | null): string {
  if (phase === "field") return "bg-emerald-500/15 shadow-[inset_3px_0_0_#34d399]";
  if (phase === "live") return "bg-amber-400/10 shadow-[inset_3px_0_0_#f6d58a]";
  if (phase === "yet") return "shadow-[inset_3px_0_0_#7dd3fc]";
  if (phase === "done") return "shadow-[inset_3px_0_0_#5c6a60]";
  return "";
}

export function PlayStatus({ phase }: { phase: PlayPhase | null }) {
  if (!phase) return null;
  const label = phase === "field" ? "On field" : phase === "live" ? "In game" : phase === "done" ? "Final" : "Yet to play";
  const tone =
    phase === "field"
      ? "bg-emerald-500/20 text-emerald-100 ring-emerald-400/50"
      : phase === "live"
        ? "bg-amber-400/15 text-amber-100 ring-amber-300/40"
        : phase === "yet"
          ? "bg-sky-400/10 text-sky-100 ring-sky-300/40"
          : "bg-white/5 text-slate-400 ring-white/10";
  return (
    <span
      data-testid="play-status"
      data-phase={phase}
      className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset", tone)}
    >
      {phase === "field" ? <span className="mr-1 h-1.5 w-1.5 rounded-full bg-emerald-300" aria-hidden /> : null}
      {label}
    </span>
  );
}

export function PlayerGameLine({ game }: { game?: GameLook | null }) {
  if (!game) return null;
  const bits = [gameScore(game), game.clock, game.points != null ? `${formatPoints(game.points)} pts` : null, game.stat_line].filter(
    (bit): bit is string => Boolean(bit),
  );
  if (!bits.length) return null;
  return (
    <p className="text-[11px] leading-snug text-slate-400" data-testid="player-game">
      {bits.join(" · ")}
    </p>
  );
}

export function opponentLabel(player: Player, week?: number): string | null {
  if (player.on_bye) return "BYE";
  const game = week != null ? player.schedule.find((item) => item.week === week) : undefined;
  const opponent = game?.opponent ?? player.opponent;
  if (!opponent) return null;
  if (game?.home === false) return `@ ${opponent}`;
  return `vs ${opponent}`;
}

export function seasonTitle(player: Player): string | undefined {
  const games = player.schedule
    .map((game) => `${game.week} ${gameLabel(game)}`)
    .join(", ");
  if (player.projection_note && games) return `${player.projection_note}. ${games}`;
  return player.projection_note ?? (games || undefined);
}

function gameLabel(game: ScheduleGame): string {
  if (!game.opponent) return "BYE";
  return `${game.home === false ? "@" : "vs"} ${game.opponent}`;
}

export function PlayerFace({
  url,
  name,
  size = "md",
}: {
  url: string | null;
  name: string;
  size?: "xs" | "sm" | "md" | "lg";
}) {
  const [failed, setFailed] = useState(false);
  const initial = name.replace(/[^A-Za-z]/g, "").slice(0, 1).toUpperCase() || "?";
  const box =
    size === "lg" ? "h-24 w-24 text-2xl" : size === "md" ? "h-16 w-16 text-lg" : size === "xs" ? "h-7 w-7 text-[10px]" : "h-12 w-12 text-sm";
  const px = size === "lg" ? 96 : size === "md" ? 64 : size === "xs" ? 28 : 48;
  const src = safeImageUrl(url);
  if (!src || failed) {
    return (
      <span
        className={cn("inline-flex shrink-0 items-center justify-center rounded-lg align-middle bg-surface-overlay font-medium text-slate-400", box)}
        aria-hidden
      >
        {initial}
      </span>
    );
  }
  return (
    <img
      src={src}
      alt=""
      width={px}
      height={px}
      loading={size === "lg" ? "eager" : "lazy"}
      decoding="async"
      className={cn("inline-block shrink-0 rounded-lg align-middle bg-surface-overlay object-cover", box)}
      onError={() => setFailed(true)}
    />
  );
}

export function upcomingGames(games: ScheduleGame[], week?: number, count = 2): ScheduleGame[] {
  const ordered = [...games].sort((a, b) => a.week - b.week);
  const upcoming = week == null ? ordered : ordered.filter((game) => game.week >= week);
  return upcoming.slice(0, count);
}

export function SeasonStrip({ games, week }: { games: ScheduleGame[]; week?: number }) {
  const shown = upcomingGames(games, week);
  if (!shown.length) return null;
  return (
    <p className="mt-1 flex max-w-xl flex-wrap gap-x-1.5 gap-y-0.5 text-[10px] leading-4 text-slate-500">
      {shown.map((game) => (
        <span key={game.week} className={cn(week != null && game.week === week && "font-semibold text-slate-100")}>
          {game.week} {gameLabel(game)}
        </span>
      ))}
    </p>
  );
}
