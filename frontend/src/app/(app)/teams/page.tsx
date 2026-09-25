"use client";

import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useStandings } from "@/lib/queries";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";

export default function TeamsPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <TeamsView leagueId={selected.id} />;
}

function TeamsView({ leagueId }: { leagueId: string }) {
  const standings = useStandings(leagueId);
  return (
    <div className="space-y-6">
      <PageHeader title="Teams" description="Open a roster. From another team you can put together a trade with the assistant." />
      <Card>
        {standings.isLoading ? (
          <SkeletonRows rows={8} />
        ) : standings.error ? (
          <ErrorState error={standings.error} onRetry={() => standings.refetch()} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-2 font-medium">#</th>
                  <th className="px-2 py-2 font-medium">Team</th>
                  <th className="px-2 py-2 font-medium">Owner</th>
                  <th className="px-2 py-2 text-right font-medium">Record</th>
                  <th className="px-5 py-2 text-right font-medium">PF</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/60">
                {standings.data?.map((row) => (
                  <tr key={row.id} className={cn(row.is_user_team && "bg-brand-soft/20")}>
                    <td className="px-5 py-2 text-slate-500">{row.rank}</td>
                    <td className="px-2 py-2 font-medium">
                      <Link href={row.is_user_team ? "/team" : `/teams/${row.id}`} className={cn("hover:underline", row.is_user_team ? "text-emerald-200" : "text-slate-100")}>
                        {row.name}
                      </Link>
                    </td>
                    <td className="px-2 py-2 text-slate-400">{row.owner_name ?? "—"}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-slate-200">{row.record}</td>
                    <td className="px-5 py-2 text-right tabular-nums text-slate-400">{formatPoints(row.points_for)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
