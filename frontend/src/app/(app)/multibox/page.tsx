"use client";

import { LeagueBox } from "@/components/league-box";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { keys } from "@/lib/queries";
import { useQueries } from "@tanstack/react-query";
const REFRESH_MS = 60_000;

export default function MultiBoxPage() {
  const { leagues, loading, select } = useLeague();
  const teams = useQueries({
    queries: leagues.map((league) => ({
      queryKey: keys.team(league.id, league.current_week),
      queryFn: () => api.leagues.team(league.id, league.current_week),
      refetchInterval: REFRESH_MS,
    })),
  });
  const matchups = useQueries({
    queries: leagues.map((league) => ({
      queryKey: keys.matchup(league.id, league.current_week),
      queryFn: () => api.leagues.matchup(league.id, league.current_week),
      refetchInterval: REFRESH_MS,
    })),
  });

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-80 w-full" />
        ))}
      </div>
    );
  }
  if (!leagues.length) return <NoLeague />;

  const alertCount = teams.reduce((sum, query) => sum + (query.data?.lineup_issues.length ? 1 : 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Multi-Box"
        description={`${leagues.length} league${leagues.length === 1 ? "" : "s"} on one screen. Scores refresh every minute.${alertCount ? ` ${alertCount} ${alertCount === 1 ? "team needs" : "teams need"} a lineup look.` : ""}`}
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {leagues.map((league, index) => {
          const team = teams[index];
          const matchup = matchups[index];
          const error = (team?.error ?? matchup?.error) as Error | null;
          return (
            <LeagueBox
              key={league.id}
              league={league}
              team={team?.data}
              matchup={matchup?.data}
              loading={!!team?.isLoading || !!matchup?.isLoading}
              error={error}
              onSelect={() => select(league.id)}
            />
          );
        })}
      </div>
    </div>
  );
}
