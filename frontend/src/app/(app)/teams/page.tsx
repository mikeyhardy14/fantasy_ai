"use client";

import { LeagueRosterBoard } from "@/components/league-rosters";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useLeagueRosters } from "@/lib/queries";
import { useState } from "react";

export default function TeamsPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <TeamsView leagueId={selected.id} currentWeek={selected.current_week} />;
}

function TeamsView({ leagueId, currentWeek }: { leagueId: string; currentWeek: number }) {
  const [week, setWeek] = useState(currentWeek);
  const rosters = useLeagueRosters(leagueId, week);
  return (
    <div className="space-y-6">
      <PageHeader
        title="Teams"
        description="Every roster in the league. Open one to look closer, or to put a trade together."
        action={
          <Select value={week} onChange={(event) => setWeek(Number(event.target.value))} aria-label="Week">
            {Array.from({ length: 18 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                Week {value}
                {value === currentWeek ? " (current)" : ""}
              </option>
            ))}
          </Select>
        }
      />
      {rosters.isLoading ? (
        <SkeletonRows rows={8} />
      ) : rosters.error ? (
        <ErrorState error={rosters.error} onRetry={() => rosters.refetch()} />
      ) : (
        <LeagueRosterBoard teams={rosters.data ?? []} week={week} />
      )}
    </div>
  );
}
