import { RosterTable } from "@/components/roster-table";
import { Card, CardHeader } from "@/components/ui/card";
import type { Team } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";

export function LeagueRosterBoard({ teams, week }: { teams: Team[]; week: number }) {
  return (
    <div className="grid items-start gap-4 xl:grid-cols-2">
      {teams.map((team, index) => {
        const yours = team.team.is_user_team;
        const href = yours ? "/team" : `/teams/${team.team.id}`;
        return (
          <Card key={team.team.id} data-testid="league-roster" className={cn(yours && "ring-1 ring-emerald-500/40")}>
            <CardHeader
              title={
                <Link href={href} className={cn("hover:underline", yours ? "text-emerald-200" : "text-slate-100")}>
                  {index + 1}. {team.team.name}
                </Link>
              }
              description={`${team.team.record}${team.team.owner_name ? ` · ${team.team.owner_name}` : ""} · Proj ${formatPoints(team.projected_points)}`}
              action={yours ? <span className="text-[11px] font-medium uppercase tracking-wide text-emerald-200">You</span> : null}
            />
            <RosterTable slots={team.starters} week={week} compact showPoints={false} />
            {team.bench.length ? (
              <div className="border-t border-surface-border">
                <p className="px-5 pt-3 text-[11px] uppercase tracking-wide text-slate-500">Bench</p>
                <RosterTable slots={team.bench} week={week} compact showPoints={false} showProjection={false} />
              </div>
            ) : null}
            {team.reserve.length ? (
              <div className="border-t border-surface-border">
                <p className="px-5 pt-3 text-[11px] uppercase tracking-wide text-slate-500">IR</p>
                <RosterTable slots={team.reserve} week={week} compact showPoints={false} showProjection={false} />
              </div>
            ) : null}
          </Card>
        );
      })}
    </div>
  );
}
