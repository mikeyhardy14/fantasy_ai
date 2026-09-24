"use client";

import type { WeeklyBriefing } from "@/lib/types";
import { cn, formatPoints, GRADE_STYLES } from "@/lib/utils";
import { Badge, PositionBadge, PriorityBadge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardBody, CardHeader } from "./ui/card";
import { ErrorState, Skeleton } from "./ui/states";

export function BriefingCard({
  briefing,
  loading,
  error,
  onGenerate,
  onRetry,
}: {
  briefing: WeeklyBriefing | undefined;
  loading: boolean;
  error: unknown;
  onGenerate: () => void;
  onRetry: () => void;
}) {
  return (
    <Card data-testid="briefing">
      <CardHeader
        title={briefing ? `Week ${briefing.week} briefing` : "Weekly briefing"}
        description={briefing ? `${briefing.team_name} · ${briefing.record}${briefing.opponent_name ? ` · vs ${briefing.opponent_name}` : ""}` : "Injuries, byes, and the moves that follow from them."}
        action={
          briefing ? (
            <Button variant="ghost" size="sm" onClick={onGenerate}>Refresh</Button>
          ) : (
            <Button size="sm" onClick={onGenerate} loading={loading}>Generate</Button>
          )
        }
      />
      <CardBody>
        {error ? (
          <ErrorState error={error} onRetry={onRetry} title="Could not build briefing" className="py-6" />
        ) : loading && !briefing ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : !briefing ? (
          <p className="text-sm text-slate-400">Generate a briefing to see injuries, byes, recommended actions and waiver targets for this week.</p>
        ) : (
          <div className="space-y-5">
            {briefing.projected_user !== null || briefing.projected_opponent !== null ? (
              <p className="text-sm text-slate-300">
                Projected matchup: <span className="font-semibold text-slate-100">{formatPoints(briefing.projected_user)}</span>
                <span className="text-slate-500"> – </span>
                <span className="font-semibold text-slate-100">{formatPoints(briefing.projected_opponent)}</span>
              </p>
            ) : null}
            {briefing.narrative ? <p className="rounded-lg border border-brand/20 bg-brand-soft/20 p-3 text-sm leading-relaxed text-emerald-100">{briefing.narrative}</p> : null}

            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                {briefing.attention_items.length} item{briefing.attention_items.length === 1 ? "" : "s"} need attention
              </h4>
              {briefing.attention_items.length ? (
                <ol className="space-y-2">
                  {briefing.attention_items.map((item, i) => (
                    <li key={i} className="flex gap-3 text-sm">
                      <span className="w-4 shrink-0 text-slate-500">{i + 1}.</span>
                      <div>
                        <div className="flex flex-wrap items-center gap-2"><span className="font-medium text-slate-100">{item.title}</span><PriorityBadge priority={item.priority} /></div>
                        <p className="text-xs text-slate-400">{item.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-slate-400">Nothing urgent. Your lineup is clear of injuries and byes.</p>
              )}
            </section>

            <div className="grid gap-5 md:grid-cols-2">
              <section>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Recommended actions</h4>
                <ul className="space-y-1.5 text-sm text-slate-300">
                  {briefing.recommended_actions.length ? briefing.recommended_actions.map((a, i) => <li key={i}>• {a}</li>) : <li className="text-slate-500">No actions required.</li>}
                </ul>
              </section>
              <section>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Waiver targets</h4>
                <ol className="space-y-1.5 text-sm text-slate-300">
                  {briefing.waiver_targets.length ? briefing.waiver_targets.map((w, i) => <li key={i}>{i + 1}. {w}</li>) : <li className="text-slate-500">No named targets (check the Waivers page).</li>}
                </ol>
              </section>
            </div>

            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Roster assessment</h4>
              <div className="flex flex-wrap gap-2">
                {briefing.roster_assessment.map((r) => (
                  <div key={r.position} className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface px-2.5 py-1.5">
                    <PositionBadge position={r.position} />
                    <span className={cn("text-xs font-medium", GRADE_STYLES[r.grade] ?? "text-slate-300")}>{r.grade}</span>
                  </div>
                ))}
              </div>
            </section>
            <Badge className="bg-slate-500/15 text-slate-400 ring-slate-500/30">{briefing.generated_by === "openai" ? "AI narrative" : "Rule-based"}</Badge>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
