"use client";

import { AnalysisCards } from "@/components/analysis-cards";
import { BriefingCard } from "@/components/briefing-card";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RecommendationList } from "@/components/recommendation-card";
import { irRulesFromSettings, LineupBoard } from "@/components/lineup-board";
import { RosterTable } from "@/components/roster-table";
import { TransactionList } from "@/components/transaction-list";
import { FlagBadges, PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { keys, useLeagueDetail, useMatchup, useRecommendations, useStandings, useTeam, useTransactions, useBriefing } from "@/lib/queries";
import type { RosterSlot } from "@/lib/types";
import { cn, formatPoints, slotNeedsAttention } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

export default function DashboardPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <DashboardSkeleton />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <Dashboard leagueId={selected.id} />;
}

function Dashboard({ leagueId }: { leagueId: string }) {
  const { selected } = useLeague();
  const team = useTeam(leagueId);
  const detail = useLeagueDetail(leagueId);
  const matchup = useMatchup(leagueId);
  const recs = useRecommendations(leagueId);
  const standings = useStandings(leagueId);
  const txs = useTransactions(leagueId);
  const [briefingRequested, setBriefingRequested] = useState(false);
  const briefing = useBriefing(leagueId, briefingRequested);
  const analyze = useMutation({ mutationFn: () => api.ai.analyze(leagueId) });
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
        week: team.data?.week ?? selected?.current_week ?? 1,
        player_id: move.playerId,
        destination: move.destination,
        slot_index: move.slotIndex,
      }),
    onSuccess: async (result) => {
      qc.setQueryData(keys.team(leagueId), result.team);
      setLineupNotice(result.message);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: async (error) => {
      setLineupNotice(error instanceof Error ? error.message : "Could not move that player.");
      await qc.invalidateQueries({ queryKey: keys.team(leagueId) });
    },
  });

  const attention: RosterSlot[] = (team.data?.starters ?? []).filter(slotNeedsAttention);
  const byeStarters = (team.data?.starters ?? []).filter((s) => s.flags.includes("BYE"));
  const injuredAll = [...(team.data?.starters ?? []), ...(team.data?.bench ?? [])].filter((s) => s.player?.injury_status);

  return (
    <div className="space-y-6">
      <PageHeader
        title={team.data?.team.name ?? selected?.user_team_name ?? selected?.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {selected?.name} · {selected?.scoring_type ?? "Custom scoring"} · Week {selected?.current_week}
          </span>
        }
        action={
          <Button size="sm" onClick={() => analyze.mutate()} loading={analyze.isPending}>
            Analyze My Team
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-x-8 gap-y-5 border-b border-surface-border pb-6 lg:grid-cols-4">
        <StatCard label="Record" value={team.data?.team.record} sub={team.data ? `${formatPoints(team.data.team.points_for)} PF · ${formatPoints(team.data.team.points_against)} PA` : undefined} loading={team.isLoading} />
        <StatCard
          label="Standing"
          value={standings.data ? `#${standings.data.find((s) => s.is_user_team)?.rank ?? "—"}` : undefined}
          sub={standings.data ? `of ${standings.data.length} teams` : undefined}
          loading={standings.isLoading}
        />
        <StatCard
          label="Projected"
          value={team.data ? formatPoints(team.data.projected_points) : undefined}
          sub={team.data?.projection_coverage === "none" ? "No projections configured" : team.data?.projection_coverage === "partial" ? "Partial coverage" : "All starters"}
          loading={team.isLoading}
        />
        <StatCard
          label={selected?.provider === "sleeper" || selected?.provider === "demo" ? "FAAB" : "Waiver"}
          value={team.data ? (team.data.team.faab_remaining !== null ? `$${team.data.team.faab_remaining}` : team.data.team.waiver_position ? `#${team.data.team.waiver_position}` : "—") : undefined}
          sub={team.data?.team.waiver_position ? `Waiver priority #${team.data.team.waiver_position}` : undefined}
          loading={team.isLoading}
        />
      </div>

      {analyze.error ? <ErrorState error={analyze.error} title="Analysis failed" onRetry={() => analyze.mutate()} className="rounded-xl border border-red-500/20" /> : null}
      {analyze.isPending ? <AnalysisSkeleton /> : null}
      {analyze.data ? <AnalysisCards result={analyze.data} /> : null}

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          {/* Matchup */}
          <Card>
            <CardHeader title={`Week ${selected?.current_week} matchup`} action={<Link href="/matchup" className="text-xs text-brand hover:underline">Full matchup</Link>} />
            <CardBody>
              {matchup.isLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : matchup.error ? (
                <ErrorState error={matchup.error} onRetry={() => matchup.refetch()} className="py-4" />
              ) : !matchup.data ? (
                <EmptyState title="No matchup this week" className="py-6" />
              ) : matchup.data.is_bye ? (
                <EmptyState title="Bye week" description="Your team does not play this week." className="py-6" />
              ) : (
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
                  <MatchupTeam name={matchup.data.user.team.name} record={matchup.data.user.team.record} points={matchup.data.user.points} projected={matchup.data.user.projected_points} align="left" highlight />
                  <div className="text-center">
                    <p className="text-[11px] uppercase tracking-wide text-slate-500">{matchup.data.status.replace("_", " ")}</p>
                    <p className="text-lg font-semibold text-slate-500">vs</p>
                  </div>
                  <MatchupTeam name={matchup.data.opponent!.team.name} record={matchup.data.opponent!.team.record} points={matchup.data.opponent!.points} projected={matchup.data.opponent!.projected_points} align="right" />
                </div>
              )}
            </CardBody>
          </Card>

          {/* Lineup */}
          <Card>
            <CardHeader
              title="Starting lineup"
              description={
                writesEnabled
                  ? "Click a starter to sub in a bench player. Drag still moves anyone to a slot, the bench, or IR."
                  : team.data?.lineup_issues.length
                    ? `${team.data.lineup_issues.length} issue${team.data.lineup_issues.length > 1 ? "s" : ""} detected`
                    : "Lineup looks legal"
              }
              action={<Link href="/team" className="text-xs text-brand hover:underline">Full roster</Link>}
            />
            {team.isLoading ? (
              <CardBody><SkeletonRows rows={9} /></CardBody>
            ) : team.error ? (
              <ErrorState error={team.error} onRetry={() => team.refetch()} />
            ) : writesEnabled && team.data ? (
              <LineupBoard
                team={team.data}
                irCapacity={Math.max(reserveSlots, reservePositions)}
                irRules={irRulesFromSettings(detail.data?.roster_settings)}
                pending={movePlayer.isPending}
                notice={lineupNotice}
                onMove={(move) => movePlayer.mutate(move)}
              />
            ) : (
              <>
                <RosterTable slots={team.data?.starters ?? []} compact week={selected?.current_week} />
                <div className="border-t border-surface-border">
                  <p className="px-5 pb-1 pt-3 text-[11px] uppercase tracking-wide text-slate-500">Bench</p>
                  <RosterTable slots={[...(team.data?.bench ?? []), ...(team.data?.reserve ?? [])]} compact showPoints={false} emptyLabel="No bench players" week={selected?.current_week} />
                </div>
                {selected?.provider === "sleeper" && detail.data && !detail.data.account.writes_enabled ? (
                  <p className="border-t border-surface-border px-5 py-3 text-xs text-slate-500">
                    Save a Sleeper token in Settings to move players from here.
                  </p>
                ) : null}
              </>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <BriefingCard
            briefing={briefing.data}
            loading={briefing.isFetching}
            error={briefing.error}
            onGenerate={() => {
              setBriefingRequested(true);
              void briefing.refetch();
            }}
            onRetry={() => briefing.refetch()}
          />

          <Card>
            <CardHeader title="Recommendations" description="From this week's roster, injuries, and byes." action={<Link href="/assistant" className="text-xs text-brand hover:underline">Ask about this team</Link>} />
            <CardBody>
              {recs.isLoading ? <SkeletonRows rows={4} /> : recs.error ? <ErrorState error={recs.error} onRetry={() => recs.refetch()} className="py-4" /> : recs.data?.length ? <RecommendationList recs={recs.data} limit={5} compact /> : <EmptyState title="No recommendations" description="Your roster has no flagged issues." className="py-6" />}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Injuries & byes" description={`${injuredAll.length} injured · ${byeStarters.length} starter${byeStarters.length === 1 ? "" : "s"} on bye`} />
            <CardBody>
              {team.isLoading ? (
                <SkeletonRows rows={3} />
              ) : attention.length || injuredAll.length ? (
                <ul className="space-y-2">
                  {[...new Map([...attention, ...injuredAll].map((s) => [s.player!.id, s])).values()].map((s) => (
                    <li key={s.player!.id} className="flex items-center justify-between gap-2 text-sm">
                      <div className="flex items-center gap-2 min-w-0">
                        <PositionBadge position={s.player!.position} />
                        <span className="truncate text-slate-100">{s.player!.name}</span>
                        <span className="text-[11px] text-slate-500">{s.slot}</span>
                      </div>
                      <FlagBadges flags={s.flags} injury={s.player!.injury_status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-400">Everyone is healthy and active this week.</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Standings" action={<Link href="/teams" className="text-xs text-brand hover:underline">All teams</Link>} />
            <CardBody className="px-0 py-0">
              {standings.isLoading ? (
                <div className="p-5"><SkeletonRows rows={6} /></div>
              ) : (
                <ul className="divide-y divide-surface-border/60">
                  {standings.data?.map((row) => (
                    <li key={row.id} className={cn("flex items-center justify-between px-5 py-2 text-sm", row.is_user_team && "bg-brand-soft/20")}>
                      <span className="flex items-center gap-3 min-w-0">
                        <span className="w-4 text-right text-xs text-slate-500">{row.rank}</span>
                        <Link href={row.is_user_team ? "/team" : `/teams/${row.id}`} className={cn("truncate hover:underline", row.is_user_team ? "font-medium text-emerald-200" : "text-slate-200")}>{row.name}</Link>
                      </span>
                      <span className="tabular-nums text-slate-400">{row.record}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Recent transactions" />
            <CardBody className="px-0 py-0">
              {txs.isLoading ? <div className="p-5"><SkeletonRows rows={4} /></div> : txs.data?.length ? <TransactionList txs={txs.data.slice(0, 6)} /> : <EmptyState title="No transactions yet" className="py-6" />}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, loading }: { label: string; value?: string; sub?: string; loading?: boolean }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      {loading ? <Skeleton className="mt-2 h-8 w-20" /> : <p className="mt-1 font-serif text-3xl tabular-nums text-slate-100">{value ?? "—"}</p>}
      {sub ? <p className="mt-1 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}

function MatchupTeam({ name, record, points, projected, align, highlight }: { name: string; record: string; points: number; projected: number | null; align: "left" | "right"; highlight?: boolean }) {
  return (
    <div className={cn(align === "right" ? "text-right" : "text-left", "min-w-0")}>
      <p className={cn("truncate text-sm font-semibold", highlight ? "text-emerald-200" : "text-slate-100")}>{name}</p>
      <p className="text-xs text-slate-500">{record}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">{formatPoints(points)}</p>
      <p className="text-xs text-slate-500">Proj {formatPoints(projected)}</p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="space-y-4" data-testid="analysis-skeleton">
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-36 w-full" />
      </div>
      <p className="text-center text-xs text-slate-500">Analyzing your roster, matchup, waivers and league settings…</p>
    </div>
  );
}
