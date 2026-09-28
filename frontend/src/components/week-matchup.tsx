"use client";

import { LivePoints } from "@/components/live-points";
import { MatchupCompare } from "@/components/matchup-compare";
import { MatchupSlate } from "@/components/matchup-slate";
import { NflSlate } from "@/components/nfl-slate";
import { RosterTable } from "@/components/roster-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeagueMatchups, useMatchup } from "@/lib/queries";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";

export function WeekMatchup({ leagueId, currentWeek }: { leagueId: string; currentWeek: number }) {
  const [week, setWeek] = useState(currentWeek);
  const matchup = useMatchup(leagueId, week, week === currentWeek ? 15_000 : false);
  const slate = useLeagueMatchups(leagueId, week, week === currentWeek ? 60_000 : false);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-serif text-2xl text-slate-100">Week {week} matchup</h2>
        <Select value={week} onChange={(event) => setWeek(Number(event.target.value))} aria-label="Matchup week">
          {Array.from({ length: 18 }, (_, index) => index + 1).map((value) => (
            <option key={value} value={value}>
              Week {value}
              {value === currentWeek ? " (current)" : ""}
            </option>
          ))}
        </Select>
      </div>

      {matchup.isLoading ? (
        <SkeletonRows rows={8} />
      ) : matchup.error ? (
        <ErrorState error={matchup.error} onRetry={() => matchup.refetch()} />
      ) : !matchup.data ? (
        <Card>
          <EmptyState title="No matchup this week" />
        </Card>
      ) : (
        <>
          <Card>
            <CardBody>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
                <Side
                  name={matchup.data.user.team.name}
                  record={matchup.data.user.team.record}
                  points={matchup.data.user.points}
                  projected={matchup.data.user.projected_points}
                  highlight
                  href="/team"
                />
                <div className="text-center">
                  <Badge className="bg-slate-500/15 text-slate-300 ring-slate-500/30">{matchup.data.status.replace("_", " ")}</Badge>
                </div>
                {matchup.data.opponent ? (
                  <Side
                    name={matchup.data.opponent.team.name}
                    record={matchup.data.opponent.team.record}
                    points={matchup.data.opponent.points}
                    projected={matchup.data.opponent.projected_points}
                    right
                    href={`/teams/${matchup.data.opponent.team.id}`}
                  />
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
                description="Each starter is compared with the player in that slot. The arrow points to whoever is ahead."
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

      {slate.data ? <MatchupSlate games={slate.data} week={week} /> : slate.isLoading ? <SkeletonRows rows={4} /> : null}

      {matchup.data?.games ? (
        <Card>
          <CardHeader title="NFL games" description="Score, clock, and the latest play." />
          <NflSlate games={matchup.data.games} />
        </Card>
      ) : null}
    </div>
  );
}

function Side({
  name,
  record,
  points,
  projected,
  highlight,
  right,
  href,
}: {
  name: string;
  record: string;
  points: number;
  projected: number | null;
  highlight?: boolean;
  right?: boolean;
  href?: string;
}) {
  const title = <p className={cn("truncate text-base font-semibold", highlight ? "text-emerald-200" : "text-slate-100")}>{name}</p>;
  return (
    <div className={cn(right && "text-right", "min-w-0")}>
      {href ? (
        <Link href={href} className="hover:underline">
          {title}
        </Link>
      ) : (
        title
      )}
      <p className="text-xs text-slate-500">{record}</p>
      <LivePoints value={formatPoints(points)} className="mt-2 block font-serif text-5xl tabular-nums text-slate-100" />
      <p className="text-xs text-slate-500">Projected {formatPoints(projected)}</p>
    </div>
  );
}
