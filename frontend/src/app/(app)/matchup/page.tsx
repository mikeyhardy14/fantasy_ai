"use client";

import { MatchupCompare } from "@/components/matchup-compare";
import { NflSlate } from "@/components/nfl-slate";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RosterTable } from "@/components/roster-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useMatchup, useStandings } from "@/lib/queries";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";

export default function MatchupPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <MatchupView leagueId={selected.id} currentWeek={selected.current_week} />;
}

function MatchupView({ leagueId, currentWeek }: { leagueId: string; currentWeek: number }) {
  const [week, setWeek] = useState(currentWeek);
  const matchup = useMatchup(leagueId, week, week === currentWeek ? 15_000 : false);
  const standings = useStandings(leagueId);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Week ${week} matchup`}
        action={
          <Select value={week} onChange={(e) => setWeek(Number(e.target.value))} aria-label="Week">
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>Week {w}{w === currentWeek ? " (current)" : ""}</option>
            ))}
          </Select>
        }
      />

      {matchup.isLoading ? (
        <SkeletonRows rows={10} />
      ) : matchup.error ? (
        <ErrorState error={matchup.error} onRetry={() => matchup.refetch()} />
      ) : !matchup.data ? (
        <Card><EmptyState title="No matchup stored for this week" description="Matchups are pulled for the current week and a few prior weeks during sync." /></Card>
      ) : (
        <>
          <Card>
            <CardBody>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
                <Side name={matchup.data.user.team.name} record={matchup.data.user.team.record} points={matchup.data.user.points} projected={matchup.data.user.projected_points} highlight href="/team" />
                <div className="text-center">
                  <Badge className="bg-slate-500/15 text-slate-300 ring-slate-500/30">{matchup.data.status.replace("_", " ")}</Badge>
                </div>
                {matchup.data.opponent ? (
                  <Side name={matchup.data.opponent.team.name} record={matchup.data.opponent.team.record} points={matchup.data.opponent.points} projected={matchup.data.opponent.projected_points} right href={`/teams/${matchup.data.opponent.team.id}`} />
                ) : (
                  <div className="text-right text-sm text-slate-400">Bye week</div>
                )}
              </div>
            </CardBody>
          </Card>

          {matchup.data.opponent ? (
            <Card>
              <CardHeader
                title="Who has the edge"
                description="Each starter is compared with the player in that slot. The arrow points to whoever is ahead. The number is the projection until that game starts, then the points scored, and it refreshes while games are on."
              />
              <MatchupCompare
                week={week}
                yours={matchup.data.user.starters}
                theirs={matchup.data.opponent.starters}
                yourName={matchup.data.user.team.name}
                theirName={matchup.data.opponent.team.name}
                calls={matchup.data.calls}
                games={matchup.data.games}
                current={week === currentWeek}
              />
            </Card>
          ) : (
            <Card>
              <CardHeader title={matchup.data.user.team.name} description="Your starters" />
              <RosterTable slots={matchup.data.user.starters} week={week} />
            </Card>
          )}
        </>
      )}

      {matchup.data?.games ? (
        <Card>
          <CardHeader title="NFL games" description="Score, clock, and the latest play. This list refreshes with the matchup." />
          <NflSlate games={matchup.data.games} />
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Standings" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-5 py-2 font-medium">#</th>
                <th className="px-2 py-2 font-medium">Team</th>
                <th className="px-2 py-2 font-medium">Owner</th>
                <th className="px-2 py-2 text-right font-medium">Record</th>
                <th className="px-2 py-2 text-right font-medium">PF</th>
                <th className="px-5 py-2 text-right font-medium">PA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/60">
              {standings.data?.map((row) => (
                <tr key={row.id} className={cn(row.is_user_team && "bg-brand-soft/20")}>
                  <td className="px-5 py-2 text-slate-500">{row.rank}</td>
                  <td className={cn("px-2 py-2 font-medium", row.is_user_team ? "text-emerald-200" : "text-slate-100")}>
                    <Link href={row.is_user_team ? "/team" : `/teams/${row.id}`} className="hover:underline">{row.name}</Link>
                  </td>
                  <td className="px-2 py-2 text-slate-400">{row.owner_name ?? "—"}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-slate-200">{row.record}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-slate-400">{formatPoints(row.points_for)}</td>
                  <td className="px-5 py-2 text-right tabular-nums text-slate-400">{formatPoints(row.points_against)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Side({ name, record, points, projected, highlight, right, href }: { name: string; record: string; points: number; projected: number | null; highlight?: boolean; right?: boolean; href?: string }) {
  const title = <p className={cn("truncate text-base font-semibold", highlight ? "text-emerald-200" : "text-slate-100")}>{name}</p>;
  return (
    <div className={cn(right && "text-right", "min-w-0")}>
      {href ? <Link href={href} className="hover:underline">{title}</Link> : title}
      <p className="text-xs text-slate-500">{record}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-slate-100">{formatPoints(points)}</p>
      <p className="text-xs text-slate-500">Projected {formatPoints(projected)}</p>
    </div>
  );
}
