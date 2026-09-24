"use client";

import { opponentLabel, PlayerFace } from "@/components/player-face";
import { PositionBadge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import type { PlayerSheet, RecentGame } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const SheetContext = createContext<((playerId: string) => void) | null>(null);

export function PlayerSheetProvider({ children }: { children: ReactNode }) {
  const [playerId, setPlayerId] = useState<string | null>(null);
  const { selected } = useLeague();
  const week = selected?.current_week;
  const sheet = useQuery({
    queryKey: ["league", selected?.id, "player-sheet", playerId, week],
    queryFn: () => api.leagues.playerSheet(selected!.id, playerId!, week),
    enabled: !!selected?.id && !!playerId,
  });

  useEffect(() => {
    if (!playerId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPlayerId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playerId]);

  return (
    <SheetContext.Provider value={selected ? setPlayerId : null}>
      {children}
      {playerId && selected ? (
        <PlayerSheetDialog
          sheet={sheet.data}
          week={week}
          loading={sheet.isLoading}
          error={sheet.error instanceof Error ? sheet.error.message : sheet.error ? "Could not load this player." : null}
          onClose={() => setPlayerId(null)}
        />
      ) : null}
    </SheetContext.Provider>
  );
}

export function PlayerName({
  id,
  name,
  className,
}: {
  id: string;
  name: string;
  className?: string;
}) {
  const open = useContext(SheetContext);
  if (!open) return <span className={className}>{name}</span>;
  return (
    <button
      type="button"
      className={cn(className, "text-left hover:underline")}
      onClick={(event) => {
        event.stopPropagation();
        open(id);
      }}
    >
      {name}
    </button>
  );
}

export function PlayerSheetDialog({
  sheet,
  week,
  loading,
  error,
  onClose,
}: {
  sheet: PlayerSheet | undefined;
  week?: number;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  const player = sheet?.player;
  const pointsLabel = sheet?.recent_games[0]?.points_label;
  const matchup = player ? opponentLabel(player, week) : null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button type="button" className="absolute inset-0 bg-[#1c1916]/40" aria-label="Close player" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={player?.name ?? "Player"}
        className="relative z-10 max-h-[85vh] w-full max-w-4xl overflow-y-auto border border-surface-border bg-surface-raised p-5 sm:p-6"
      >
        {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
        {error ? <p className="text-sm text-red-300">{error}</p> : null}
        {player ? (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <PlayerFace url={player.headshot_url} name={player.name} />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <PositionBadge position={player.position} />
                  <h2 className="truncate font-serif text-2xl text-slate-100">{player.name}</h2>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {player.nfl_team ?? "FA"}
                  {matchup ? ` · ${matchup}` : ""}
                  {player.projected_points != null ? ` · Proj ${formatPoints(player.projected_points)}` : ""}
                </p>
              </div>
            </div>

            <section>
              <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Why this projection</h3>
              {player.projection_lines.length ? (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                        <th className="py-1 font-medium">Prop</th>
                        <th className="py-1 text-right font-medium">Line</th>
                        <th className="py-1 text-right font-medium">Odds</th>
                        <th className="py-1 text-right font-medium">Scoring</th>
                        <th className="py-1 text-right font-medium">Pts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {player.projection_lines.map((line) => (
                        <tr key={line.label} className="border-t border-surface-border/70">
                          <td className="py-1.5 text-slate-200">{line.label}</td>
                          <td className="py-1.5 text-right tabular-nums text-slate-100">{formatStat(line.line)}</td>
                          <td className="py-1.5 text-right tabular-nums text-slate-400">
                            {line.odds ? `${line.odds}${line.probability != null ? ` (${Math.round(line.probability * 100)}%)` : ""}` : "—"}
                          </td>
                          <td className="py-1.5 text-right tabular-nums text-slate-400">× {formatStat(line.weight)}</td>
                          <td className="py-1.5 text-right tabular-nums text-slate-100">{formatStat(line.points)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <ul className="mt-2 space-y-1.5 text-sm text-slate-200">
                {player.projection_reasons.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>

            <section>
              <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Recent games</h3>
              {sheet?.recent_games.length ? <RecentStats games={sheet.recent_games} /> : null}
              {pointsLabel ? <p className="mt-2 text-[11px] text-slate-500">Points: {pointsLabel}.</p> : null}
              {sheet?.games_note ? <p className="mt-2 text-sm text-slate-500">{sheet.games_note}</p> : null}
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}

const STAT_COLUMNS: [keyof RecentGame["stats"] | string, string][] = [
  ["pass_yd", "Pass yds"],
  ["pass_td", "Pass TD"],
  ["pass_int", "INT"],
  ["rush_yd", "Rush yds"],
  ["rush_td", "Rush TD"],
  ["rec", "Rec"],
  ["rec_yd", "Rec yds"],
  ["rec_td", "Rec TD"],
  ["fum_lost", "Fum"],
  ["sack", "Sacks"],
  ["int", "Def INT"],
  ["fum_rec", "Fum rec"],
  ["def_td", "Def TD"],
  ["pts_allow", "Pts allowed"],
  ["fgm", "FG"],
  ["xpm", "XP"],
];

function formatStat(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  if (Math.abs(rounded - Math.round(rounded)) < 1e-9) return String(Math.round(rounded));
  if (Math.abs(rounded * 10 - Math.round(rounded * 10)) < 1e-9) return rounded.toFixed(1);
  return rounded.toFixed(2);
}

function RecentStats({ games }: { games: RecentGame[] }) {
  const columns = STAT_COLUMNS.filter(([key]) => games.some((game) => game.stats?.[key] != null));
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className="py-1 pr-3 font-medium">Wk</th>
            <th className="py-1 pr-3 font-medium">Opp</th>
            {columns.map(([key, label]) => (
              <th key={key} className="py-1 pr-3 text-right font-medium">
                {label}
              </th>
            ))}
            <th className="py-1 text-right font-medium">Pts</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => (
            <tr key={game.week} className="border-t border-surface-border/70">
              <td className="py-1.5 pr-3 tabular-nums text-slate-400">{game.week}</td>
              <td className="py-1.5 pr-3 text-slate-300">
                {game.opponent ? `${game.home === false ? "@" : "vs"} ${game.opponent}` : "—"}
              </td>
              {columns.map(([key]) => (
                <td key={key} className="py-1.5 pr-3 text-right tabular-nums text-slate-200">
                  {game.stats?.[key] == null ? "—" : formatStat(game.stats[key])}
                </td>
              ))}
              <td className="py-1.5 text-right tabular-nums text-slate-100">{formatPoints(game.fantasy_points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
