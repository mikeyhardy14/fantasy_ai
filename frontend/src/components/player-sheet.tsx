"use client";

import { gameScore } from "@/components/player-game";
import { opponentLabel, PlayerFace } from "@/components/player-face";
import { useToast } from "@/components/toast";
import { PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { useLeagueDetail } from "@/lib/queries";
import type { PlayerSheet, RecentGame, SuggestedTrade } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const SheetContext = createContext<((playerId: string) => void) | null>(null);

export function PlayerSheetProvider({ children }: { children: ReactNode }) {
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [draft, setDraft] = useState<SuggestedTrade | null>(null);
  const { selected } = useLeague();
  const detail = useLeagueDetail(selected?.id);
  const toast = useToast();
  const week = selected?.current_week;
  const writes = selected?.provider === "sleeper" && !!detail.data?.account.writes_enabled;
  const sheet = useQuery({
    queryKey: ["league", selected?.id, "player-sheet", playerId, week],
    queryFn: () => api.leagues.playerSheet(selected!.id, playerId!, week),
    enabled: !!selected?.id && !!playerId,
  });
  const suggest = useMutation({
    mutationFn: () => api.ai.suggestTrade(selected!.id, playerId!),
    onSuccess: (offer) => setDraft(offer),
  });
  const send = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error("Ask for an offer first.");
      return api.leagues.proposeTrade(selected!.id, {
        give: draft.give.map((player) => player.id),
        receive: draft.receive.map((player) => player.id),
      });
    },
    onSuccess: (result) => {
      toast(result.message);
      setDraft(null);
      setPlayerId(null);
    },
  });

  useEffect(() => {
    setDraft(null);
    suggest.reset();
    send.reset();
    // A new player starts a new offer. Resetting the mutations here is the point.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerId]);

  useEffect(() => {
    if (!playerId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPlayerId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playerId]);

  const otherTeam = sheet.data?.rostered_on && !sheet.data.rostered_on.is_user_team;

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
          onTradeFor={otherTeam ? () => suggest.mutate() : undefined}
          tradePending={suggest.isPending}
          tradeDraft={draft}
          tradeError={
            suggest.error instanceof Error
              ? suggest.error.message
              : send.error instanceof Error
                ? send.error.message
                : null
          }
          canSend={writes}
          sending={send.isPending}
          onSend={draft ? () => send.mutate() : undefined}
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
  onTradeFor,
  tradePending = false,
  tradeDraft = null,
  tradeError = null,
  canSend = false,
  sending = false,
  onSend,
}: {
  sheet: PlayerSheet | undefined;
  week?: number;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onTradeFor?: () => void;
  tradePending?: boolean;
  tradeDraft?: SuggestedTrade | null;
  tradeError?: string | null;
  canSend?: boolean;
  sending?: boolean;
  onSend?: () => void;
}) {
  const player = sheet?.player;
  const pointsLabel = sheet?.recent_games[0]?.points_label;
  const matchup = player ? opponentLabel(player, week) : null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button type="button" className="veil-enter absolute inset-0 bg-[#1c1916]/40" aria-label="Close player" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={player?.name ?? "Player"}
        className="sheet-enter relative z-10 max-h-[85vh] w-full max-w-4xl overflow-y-auto border border-surface-border bg-surface-raised p-5 shadow-card sm:p-6"
      >
        {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
        {error ? <p className="text-sm text-red-300">{error}</p> : null}
        {player ? (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <PlayerFace url={player.headshot_url} name={player.name} size="lg" />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <PositionBadge position={player.position} />
                  <h2 className="truncate font-serif text-2xl text-slate-100">{player.name}</h2>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {player.nfl_team ?? "FA"}
                  {matchup ? ` · ${matchup}` : ""}
                  {player.season_points != null ? ` · ${formatPoints(player.season_points)} total` : ""}
                  {player.projected_points != null ? ` · Proj ${formatPoints(player.projected_points)}` : ""}
                </p>
                <p className="mt-1 text-sm text-slate-200" data-testid="rostered-on">
                  {sheet?.rostered_on
                    ? sheet.rostered_on.is_user_team
                      ? "On your team"
                      : `On ${sheet.rostered_on.team_name}${sheet.rostered_on.owner_name ? ` · ${sheet.rostered_on.owner_name}` : ""}`
                    : "Free agent"}
                </p>
              </div>
            </div>

            <section data-testid="this-week" className="border-t border-surface-border pt-4">
              <h3 className="text-[11px] uppercase tracking-wide text-slate-500">This week</h3>
              <p className="mt-2 text-sm text-slate-100">Projected {formatPoints(player.projected_points)}</p>
              {sheet?.game ? (
                <div className="mt-1 space-y-1 text-sm text-slate-300">
                  {gameScore(sheet.game) ? <p>{gameScore(sheet.game)}</p> : null}
                  {sheet.game.clock ? <p>{sheet.game.clock}</p> : null}
                  {sheet.game.points != null ? <p>{formatPoints(sheet.game.points)} fantasy points</p> : null}
                  {sheet.game.stat_line ? <p>{sheet.game.stat_line}</p> : null}
                </div>
              ) : (
                <p className="mt-1 text-sm text-slate-500">No live game posted for this week.</p>
              )}
            </section>

            {onTradeFor ? (
              <div className="space-y-3 border-t border-surface-border pt-4">
                <Button type="button" size="sm" data-testid="trade-for" loading={tradePending} onClick={onTradeFor}>
                  Trade for
                </Button>
                {tradeDraft ? (
                  <div className="space-y-2 text-sm">
                    <p className="text-slate-200" data-testid="trade-draft">{tradeDraft.message}</p>
                    <p className="text-slate-400">
                      You give {tradeDraft.give.map((side) => side.name).join(", ")} for {tradeDraft.receive.map((side) => side.name).join(", ")}.
                    </p>
                    {canSend ? (
                      <Button type="button" size="sm" data-testid="trade-send" loading={sending} onClick={onSend}>
                        Send
                      </Button>
                    ) : (
                      <p className="text-xs text-slate-500">Save a Sleeper token in Settings to send an offer.</p>
                    )}
                  </div>
                ) : null}
                {tradeError ? <p className="text-sm text-red-300">{tradeError}</p> : null}
              </div>
            ) : null}

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
