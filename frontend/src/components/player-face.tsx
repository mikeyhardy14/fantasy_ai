"use client";

import type { Player, ScheduleGame } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useState } from "react";

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
  size?: "sm" | "md";
}) {
  const [failed, setFailed] = useState(false);
  const initial = name.replace(/[^A-Za-z]/g, "").slice(0, 1).toUpperCase() || "?";
  const box = size === "sm" ? "h-7 w-7 text-[10px]" : "h-8 w-8 text-[11px]";
  if (!url || failed) {
    return (
      <span
        className={cn("inline-flex shrink-0 items-center justify-center bg-surface-overlay font-medium text-slate-400", box)}
        aria-hidden
      >
        {initial}
      </span>
    );
  }
  return (
    <img
      src={url}
      alt=""
      className={cn("shrink-0 bg-surface-overlay object-cover", box)}
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
