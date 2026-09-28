"use client";

import { LeagueRosterBoard } from "@/components/league-rosters";
import { TeamComparePanel } from "@/components/team-compare";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useLeagueRosters } from "@/lib/queries";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

export default function TeamsPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <TeamsView leagueId={selected.id} currentWeek={selected.current_week} />;
}

function TeamsView({ leagueId, currentWeek }: { leagueId: string; currentWeek: number }) {
  const params = useSearchParams();
  const compareId = params.get("compare");
  const [week, setWeek] = useState(currentWeek);
  const [layout, setLayout] = useState<"list" | "rosters" | "compare">(compareId ? "compare" : "list");
  const [query, setQuery] = useState("");
  const rosters = useLeagueRosters(leagueId, week);
  const needle = query.trim().toLowerCase();
  const teams = useMemo(() => {
    const rows = rosters.data ?? [];
    if (!needle) return rows;
    return rows.filter((team) => {
      const name = team.team.name.toLowerCase();
      const owner = (team.team.owner_name ?? "").toLowerCase();
      return name.includes(needle) || owner.includes(needle);
    });
  }, [rosters.data, needle]);
  return (
    <div className="space-y-6">
      <PageHeader
        title="Teams"
        description="Open a team, scroll every roster, or compare any two with the numbers and a write-up."
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter by team or manager"
          aria-label="Filter teams"
        />
        <div className="flex shrink-0 gap-2">
          <Button type="button" size="sm" variant={layout === "list" ? "primary" : "secondary"} onClick={() => setLayout("list")}>
            List
          </Button>
          <Button type="button" size="sm" variant={layout === "rosters" ? "primary" : "secondary"} onClick={() => setLayout("rosters")}>
            All rosters
          </Button>
          <Button type="button" size="sm" variant={layout === "compare" ? "primary" : "secondary"} onClick={() => setLayout("compare")}>
            Compare
          </Button>
        </div>
      </div>
      {rosters.isLoading ? (
        <SkeletonRows rows={8} />
      ) : rosters.error ? (
        <ErrorState error={rosters.error} onRetry={() => rosters.refetch()} />
      ) : layout === "compare" ? (
        <TeamComparePanel leagueId={leagueId} week={week} teams={rosters.data ?? []} initialRight={compareId} />
      ) : layout === "rosters" ? (
        <LeagueRosterBoard teams={teams} week={week} />
      ) : (
        <Card>
          <CardBody className="px-0 py-0">
            {teams.length ? (
              <ul className="divide-y divide-surface-border/60">
                {teams.map((team, index) => {
                  const href = team.team.is_user_team ? "/team" : `/teams/${team.team.id}`;
                  return (
                    <li key={team.team.id}>
                      <Link
                        href={href}
                        className={cn("flex items-center gap-3 px-5 py-3 hover:bg-surface-overlay/50", team.team.is_user_team && "bg-emerald-500/10")}
                      >
                        <span className="w-6 tabular-nums text-xs text-slate-500">{index + 1}</span>
                        <span className="min-w-0 flex-1">
                          <span className={cn("block truncate font-medium", team.team.is_user_team ? "text-emerald-200" : "text-slate-100")}>
                            {team.team.name}
                          </span>
                          <span className="block truncate text-[11px] text-slate-500">
                            {team.team.owner_name ?? "Manager"} · {team.team.record}
                          </span>
                        </span>
                        <span className="text-right text-xs text-slate-400">
                          <span className="block tabular-nums text-slate-200">{formatPoints(team.team.points_for)} PF</span>
                          <span className="block tabular-nums">Proj {formatPoints(team.projected_points)}</span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="px-5 py-6 text-sm text-slate-500">No teams match that filter.</p>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
