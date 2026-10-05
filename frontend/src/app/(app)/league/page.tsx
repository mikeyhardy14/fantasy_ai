"use client";

import { AnalysisCards } from "@/components/advice/analysis-cards";
import { BriefingCard } from "@/components/advice/briefing-card";
import { RecommendationList } from "@/components/advice/recommendation-card";
import { AssistantDock } from "@/components/chat/assistant-dock";
import { LeagueGames } from "@/components/matchup/matchup-slate";
import { slotsFromMatchups } from "@/components/matchup/hot-list";
import { MatchupCompare } from "@/components/matchup/matchup-compare";
import { NflSlate } from "@/components/matchup/nfl-slate";
import { PlayerFace, PlayStatus, playPhase, playRowClass } from "@/components/player/player-face";
import { PlayerName } from "@/components/player/player-sheet";
import { irRulesFromSettings, LineupBoard } from "@/components/roster/lineup-board";
import { LivePoints, UpdatedAgo } from "@/components/shell/live-points";
import { NoLeague } from "@/components/shell/no-league";
import { useToast } from "@/components/shell/toast";
import { TransactionList } from "@/components/trades/transaction-list";
import { FlagBadges } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Pop } from "@/components/ui/pop";
import { ErrorState, Skeleton, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { recAction, recKey, readDismissed, writeDismissed } from "@/lib/rec-actions";
import { keys, useBriefing, useHealth, useLeagueDetail, useLeagueMatchups, useMatchup, useRecommendations, useStandings, useTeam, useTransactions } from "@/lib/queries";
import { fantasyLabel } from "@/lib/matchup-status";
import { boardWeek } from "@/lib/week";
import type { Recommendation, RosterSlot } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

type Panel = "lineup" | "moves" | "briefing" | "recs" | "analysis" | null;

export default function LeaguePage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <LeagueSkeleton />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <LeagueView leagueId={selected.id} />;
}

function LeagueView({ leagueId }: { leagueId: string }) {
  const { selected } = useLeague();
  const team = useTeam(leagueId);
  const standings = useStandings(leagueId);
  const providerWeek = selected?.current_week ?? team.data?.week ?? 1;
  const providerBoard = useMatchup(leagueId, providerWeek, false);
  const currentWeek = boardWeek(providerWeek, providerBoard.data?.games);
  const [picked, setPicked] = useState<number | null>(null);
  const week = picked ?? currentWeek;

  useEffect(() => {
    setPicked(null);
  }, [leagueId]);
  const leagueGames = useLeagueMatchups(leagueId, week, week === currentWeek ? 60_000 : false);
  const weekGames = useMatchup(leagueId, week, week === currentWeek ? 15_000 : false);
  const extras = weekGames.isFetched || leagueGames.isFetched;
  const detail = useLeagueDetail(leagueId, extras);
  const recs = useRecommendations(leagueId, extras);
  const txs = useTransactions(leagueId, extras);
  const health = useHealth(extras);
  const toast = useToast();
  const router = useRouter();
  const [briefingRequested, setBriefingRequested] = useState(false);
  const briefing = useBriefing(leagueId, briefingRequested);
  const [panel, setPanel] = useState<Panel>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const analyze = useMutation({
    mutationFn: () => api.ai.analyze(leagueId),
    onSuccess: () => setPanel("analysis"),
  });
  const qc = useQueryClient();
  const [lineupNotice, setLineupNotice] = useState<string | null>(null);
  const writesEnabled = selected?.provider === "sleeper" && !!detail.data?.account.writes_enabled;
  const reserveSlots = Number(detail.data?.roster_settings?.reserve_slots ?? 0);
  const reservePositions = Array.isArray(detail.data?.roster_settings?.roster_positions)
    ? (detail.data?.roster_settings.roster_positions as string[]).filter((slot) => slot === "IR").length
    : 0;
  const movePlayer = useMutation({
    mutationFn: (move: { playerId: string; destination: "starter" | "bench" | "ir"; slotIndex?: number }) =>
      api.leagues.movePlayer(leagueId, {
        week,
        player_id: move.playerId,
        destination: move.destination,
        slot_index: move.slotIndex,
      }),
    onSuccess: async (result) => {
      qc.setQueryData(keys.team(leagueId), result.team);
      setLineupNotice(null);
      toast(result.message);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: async (error) => {
      setLineupNotice(error instanceof Error ? error.message : "Could not move that player.");
      await qc.invalidateQueries({ queryKey: keys.team(leagueId) });
    },
  });

  const liveNfl = weekGames.data?.games?.filter((game) => game.state === "in").length ?? 0;
  const rank = standings.data?.find((row) => row.is_user_team)?.rank;
  const faab = team.data?.team.faab_remaining != null ? `$${team.data.team.faab_remaining}` : team.data?.team.waiver_position ? `#${team.data.team.waiver_position}` : "—";
  const notes = (recs.data ?? []).filter((rec) => !dismissed.includes(recKey(rec)));

  useEffect(() => {
    setDismissed(readDismissed(leagueId));
  }, [leagueId]);

  function disableNote(rec: Recommendation) {
    setDismissed((current) => {
      const next = [...new Set([...current, recKey(rec)])];
      writeDismissed(leagueId, next);
      return next;
    });
  }

  const applyNote = useMutation({
    mutationFn: async (rec: Recommendation) => {
      const action = recAction(rec);
      if (action === "open") return { kind: "open" as const, rec };
      if (!writesEnabled) throw new Error("Save a Sleeper token in Settings to do this.");
      if (action === "do") {
        const slotIndex =
          typeof rec.data.slot_index === "number"
            ? rec.data.slot_index
            : team.data?.starters.find((slot) => slot.slot === rec.data.slot)?.slot_index;
        if (slotIndex == null) throw new Error("Could not find that lineup slot.");
        return { kind: "write" as const, rec, result: await api.leagues.movePlayer(leagueId, { week, player_id: rec.players[0], destination: "starter", slot_index: slotIndex }) };
      }
      if (action === "add") {
        return { kind: "write" as const, rec, result: await api.leagues.addPlayer(leagueId, rec.players[0]) };
      }
      if (action === "drop") {
        return { kind: "write" as const, rec, result: await api.leagues.claimRoster(leagueId, { drop_player_id: rec.players[0] }) };
      }
      throw new Error("Nothing to do for that note.");
    },
    onSuccess: async (payload) => {
      if (payload.kind === "open") {
        if (payload.rec.type === "TRADE_TARGET") router.push("/trades");
        else if (payload.rec.type === "ROSTER_WEAKNESS") router.push("/players");
        else setPanel("lineup");
        return;
      }
      toast(payload.result.message);
      disableNote(payload.rec);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error) => {
      toast(error instanceof Error ? error.message : "Could not do that.");
    },
  });

  function openBriefing() {
    setBriefingRequested(true);
    setPanel("briefing");
    void briefing.refetch();
  }

  return (
    <div className="flex flex-col gap-2 pb-20">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h1 className="truncate font-serif text-lg text-slate-100">{team.data?.team.name ?? selected?.user_team_name ?? selected?.name}</h1>
        <Stat value={team.data?.team.record} />
        <Stat value={rank != null ? `#${rank}` : undefined} />
        <Stat value={team.data ? formatPoints(team.data.projected_points) : undefined} />
        <Stat value={team.data ? faab : undefined} />
        {team.isFetched ? <UpdatedAgo at={team.dataUpdatedAt} /> : null}
        <div className="ml-auto flex items-center gap-2">
          <Select className="h-8 w-[7.5rem] text-xs" value={week} onChange={(event) => setPicked(Number(event.target.value))} aria-label="League week">
            {Array.from({ length: 18 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                Wk {value}
                {value === currentWeek ? " · now" : ""}
              </option>
            ))}
          </Select>
          <Button size="sm" onClick={() => analyze.mutate()} loading={analyze.isPending}>
            Analyze
          </Button>
        </div>
      </div>
      {analyze.error ? <ErrorState error={analyze.error} title="Analysis failed" onRetry={() => analyze.mutate()} className="rounded-lg border border-red-500/20" /> : null}

      <div className="grid items-start gap-3 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-6">
          <Pane title="Games" action={<span className="text-[11px] text-slate-500">Wk {week}</span>}>
            {leagueGames.isLoading ? (
              <div className="p-3"><SkeletonRows rows={6} /></div>
            ) : leagueGames.error ? (
              <ErrorState error={leagueGames.error} onRetry={() => leagueGames.refetch()} />
            ) : (
              <LeagueGames games={leagueGames.data ?? []} week={week} nfl={weekGames.data?.games} current={week === currentWeek} />
            )}
          </Pane>
          <Pane title="NFL Games" action={liveNfl ? <span className="text-[11px] font-medium text-red-300">{liveNfl} live</span> : null}>
            {weekGames.isLoading ? (
              <div className="p-3"><SkeletonRows rows={8} /></div>
            ) : weekGames.data?.games?.length ? (
              <NflSlate games={weekGames.data.games} compact slots={slotsFromMatchups(leagueGames.data ?? [])} />
            ) : (
              <p className="px-3 py-3 text-xs text-slate-500">No NFL games this week.</p>
            )}
          </Pane>
        </div>

        <Pane
          title="Matchup"
          className="lg:col-span-4"
          action={
            <button type="button" className="text-[11px] text-emerald-200 hover:underline" onClick={() => setPanel("lineup")}>
              Lineup
            </button>
          }
        >
          {weekGames.isLoading ? (
            <div className="p-3"><SkeletonRows rows={8} /></div>
          ) : weekGames.error ? (
            <ErrorState error={weekGames.error} onRetry={() => weekGames.refetch()} />
          ) : !weekGames.data ? (
            <p className="px-3 py-4 text-xs text-slate-400">No matchup this week.</p>
          ) : (
            <>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 border-b border-white/10 px-3 py-1.5">
                <MatchSide
                  name={weekGames.data.user.team.name}
                  record={weekGames.data.user.team.record}
                  points={weekGames.data.user.points}
                  projected={weekGames.data.user.projected_points}
                  href="/team"
                  highlight
                />
                <span className="text-[10px] uppercase tracking-wide text-slate-500">
                  {fantasyLabel(
                    weekGames.data.status,
                    [...weekGames.data.user.starters, ...(weekGames.data.opponent?.starters ?? [])],
                    weekGames.data.games,
                  )}
                </span>
                {weekGames.data.opponent ? (
                  <MatchSide
                    name={weekGames.data.opponent.team.name}
                    record={weekGames.data.opponent.team.record}
                    points={weekGames.data.opponent.points}
                    projected={weekGames.data.opponent.projected_points}
                    href={`/teams/${weekGames.data.opponent.team.id}`}
                    right
                  />
                ) : (
                  <p className="text-right text-xs text-slate-400">Bye</p>
                )}
              </div>
              {weekGames.data.opponent ? (
                <MatchupCompare
                  compact
                  week={week}
                  yours={weekGames.data.user.starters}
                  theirs={weekGames.data.opponent.starters}
                  yourName={weekGames.data.user.team.name}
                  theirName={weekGames.data.opponent.team.name}
                  calls={weekGames.data.calls}
                  games={weekGames.data.games}
                  current={week === currentWeek}
                />
              ) : (
                <ul>
                  {weekGames.data.user.starters.map((slot, index) => (
                    <StarterRow key={`${slot.slot}-${slot.player?.id ?? index}`} slot={slot} />
                  ))}
                </ul>
              )}
            </>
          )}
        </Pane>

        <div className="flex min-h-0 flex-col gap-2 lg:col-span-2">
          <Pane title="Standings" className="flex-1" action={<Link href="/teams" className="text-[11px] text-emerald-200 hover:underline">All</Link>}>
            {standings.isLoading ? (
              <div className="p-3"><SkeletonRows rows={8} /></div>
            ) : (
              <ul>
                {standings.data?.map((row) => (
                  <li key={row.id} className={cn("flex items-center justify-between gap-2 px-3 py-1 text-xs", row.is_user_team && "bg-emerald-400/10")}>
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="w-4 text-right text-slate-500">{row.rank}</span>
                      <Link href={row.is_user_team ? "/team" : `/teams/${row.id}`} className={cn("truncate hover:underline", row.is_user_team ? "font-medium text-emerald-100" : "text-slate-200")}>
                        {row.name}
                      </Link>
                    </span>
                    <span className="shrink-0 tabular-nums text-slate-400">{row.record}</span>
                  </li>
                ))}
              </ul>
            )}
          </Pane>
          <div className="grid grid-cols-3 gap-1">
            <Quick label="Notes" hint={notes.length} onClick={() => setPanel("recs")} />
            <Quick label="Moves" hint={`${txs.data?.length ?? 0}`} onClick={() => setPanel("moves")} />
            <Quick label="Brief" hint={briefing.data ? "Ready" : "Open"} onClick={openBriefing} />
          </div>
        </div>
      </div>

      {panel === "lineup" ? (
        <Pop title="Lineup" onClose={() => setPanel(null)} wide>
          {writesEnabled && team.data ? (
            <LineupBoard
              team={team.data}
              irCapacity={Math.max(reserveSlots, reservePositions)}
              irRules={irRulesFromSettings(detail.data?.roster_settings)}
              pending={movePlayer.isPending}
              notice={lineupNotice}
              onMove={(move) => movePlayer.mutate(move)}
            />
          ) : (
            <p className="p-4 text-sm text-slate-400">Save a Sleeper token in Settings to move players from here.</p>
          )}
        </Pop>
      ) : null}
      {panel === "moves" ? (
        <Pop title="Moves" onClose={() => setPanel(null)}>
          {txs.data?.length ? <TransactionList txs={txs.data.slice(0, 12)} /> : <p className="p-4 text-sm text-slate-400">No transactions yet.</p>}
        </Pop>
      ) : null}
      {panel === "briefing" ? (
        <Pop title="Briefing" onClose={() => setPanel(null)} wide>
          <BriefingCard
            briefing={briefing.data}
            loading={briefing.isFetching}
            error={briefing.error}
            onGenerate={openBriefing}
            onRetry={() => briefing.refetch()}
          />
        </Pop>
      ) : null}
      {panel === "recs" ? (
        <Pop title="Notes" onClose={() => setPanel(null)}>
          <div className="px-4 py-2">
            {notes.length ? (
              <RecommendationList
                recs={notes}
                onDo={(rec) => applyNote.mutate(rec)}
                onDisable={disableNote}
                pendingKey={applyNote.isPending && applyNote.variables ? recKey(applyNote.variables) : null}
              />
            ) : (
              <p className="py-6 text-sm text-slate-400">No notes right now.</p>
            )}
          </div>
        </Pop>
      ) : null}
      {panel === "analysis" && analyze.data ? (
        <Pop title="Analysis" onClose={() => setPanel(null)} wide>
          <div className="p-3">
            <AnalysisCards result={analyze.data} />
          </div>
        </Pop>
      ) : null}

      <AssistantDock leagueId={leagueId} aiEnabled={health.data?.ai_enabled} />
    </div>
  );
}

function Pane({ title, action, children, className }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("flex min-h-0 flex-col overflow-hidden", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-1.5">
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{title}</h3>
        {action}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </Card>
  );
}

function Stat({ value }: { value?: string }) {
  return <span className="text-sm tabular-nums text-slate-200">{value ?? "—"}</span>;
}

function Quick({ label, hint, onClick }: { label: string; hint: string | number; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-lg border border-white/10 bg-surface-raised/95 px-2 py-1.5 text-left hover:bg-white/5">
      <span className="block text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-xs text-slate-100">{hint}</span>
    </button>
  );
}

function MatchSide({
  name,
  record,
  points,
  projected,
  href,
  highlight,
  right,
}: {
  name: string;
  record: string;
  points: number;
  projected: number | null;
  href: string;
  highlight?: boolean;
  right?: boolean;
}) {
  return (
    <div className={cn("min-w-0", right && "text-right")}>
      <Link href={href} className={cn("block truncate text-xs font-medium hover:underline", highlight ? "text-emerald-100" : "text-slate-100")}>
        {name}
      </Link>
      <LivePoints value={formatPoints(points)} className="block font-serif text-xl tabular-nums text-slate-100" />
      <p className="text-[10px] text-slate-500">{record} · {formatPoints(projected)}</p>
    </div>
  );
}

function StarterRow({ slot }: { slot: RosterSlot }) {
  const player = slot.player;
  const phase = playPhase(slot.game, player?.position, player?.nfl_team);
  return (
    <li className={cn("flex items-center gap-1.5 px-2 py-1", playRowClass(phase))} data-testid="roster-row">
      <span className="w-8 shrink-0 text-[10px] uppercase tracking-wide text-slate-500">{slot.slot.replace("_", " ")}</span>
      {player ? (
        <>
          <PlayerFace url={player.headshot_url} name={player.name} size="xs" />
          <PlayerName id={player.id} name={player.name} className="min-w-0 flex-1 truncate text-xs text-slate-100" />
          <PlayStatus phase={phase} />
          <FlagBadges flags={slot.flags} injury={player.injury_status} />
          <span className="w-8 shrink-0 text-right tabular-nums text-xs text-slate-200">{formatPoints(slot.points)}</span>
        </>
      ) : (
        <span className="text-xs italic text-red-300">Empty</span>
      )}
    </li>
  );
}

function LeagueSkeleton() {
  return (
    <div className="flex flex-col gap-2 pb-20">
      <Skeleton className="h-7 w-64" />
      <div className="grid items-start gap-3 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-6">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
        <Skeleton className="h-[28rem] w-full lg:col-span-4" />
        <Skeleton className="h-72 w-full lg:col-span-2" />
      </div>
    </div>
  );
}
