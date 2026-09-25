"use client";

import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RosterTable } from "@/components/roster-table";
import { TradeOffer } from "@/components/trade-offer";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useOtherTeam, useTeam } from "@/lib/queries";
import { formatPoints } from "@/lib/utils";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

export default function OtherTeamPage() {
  const params = useParams<{ teamId: string }>();
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <OtherTeamView leagueId={selected.id} teamId={params.teamId} currentWeek={selected.current_week} />;
}

function OtherTeamView({ leagueId, teamId, currentWeek }: { leagueId: string; teamId: string; currentWeek: number }) {
  const [week, setWeek] = useState(currentWeek);
  const team = useOtherTeam(leagueId, teamId, week);
  const mine = useTeam(leagueId, week);
  const view = team.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={view?.team.name ?? "Team"}
        description={view ? `${view.team.record}${view.team.owner_name ? ` · ${view.team.owner_name}` : ""}` : undefined}
        action={
          <Select value={week} onChange={(event) => setWeek(Number(event.target.value))} aria-label="Week">
            {Array.from({ length: 18 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>Week {value}{value === currentWeek ? " (current)" : ""}</option>
            ))}
          </Select>
        }
      />
      {team.isLoading ? (
        <SkeletonRows rows={10} />
      ) : team.error ? (
        <ErrorState error={team.error} onRetry={() => team.refetch()} />
      ) : view ? (
        <>
          {view.team.is_user_team ? (
            <Card>
              <CardHeader
                title="This is your team"
                description={`Projected ${formatPoints(view.projected_points)}`}
                action={<Link href="/team"><Button size="sm" variant="secondary">Open My Team</Button></Link>}
              />
            </Card>
          ) : null}
          <Card>
            <CardHeader title="Starters" description={`Projected ${formatPoints(view.projected_points)} (${view.projection_coverage} coverage)`} />
            <RosterTable slots={view.starters} week={week} />
          </Card>
          <Card>
            <CardHeader title="Bench" />
            <RosterTable slots={view.bench} showPoints={false} emptyLabel="Bench is empty" week={week} />
          </Card>
          {view.reserve.length ? (
            <Card>
              <CardHeader title="IR / Taxi" />
              <RosterTable slots={view.reserve} showPoints={false} week={week} />
            </Card>
          ) : null}
          {!view.team.is_user_team && mine.data ? <TradeOffer leagueId={leagueId} mine={mine.data} opponent={view} /> : null}
        </>
      ) : null}
    </div>
  );
}
