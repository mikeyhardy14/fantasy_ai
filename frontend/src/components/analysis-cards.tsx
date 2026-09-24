import type { TeamAnalysisResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, PositionBadge, PriorityBadge } from "./ui/badge";
import { Card, CardBody, CardHeader } from "./ui/card";

function Bullets({ items, tone = "default" }: { items: string[]; tone?: "default" | "good" | "bad" }) {
  if (!items.length) return <p className="text-xs italic text-slate-500">Nothing to report.</p>;
  return (
    <ul className="space-y-1.5 text-sm text-slate-300">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2">
          <span className={cn("mt-2 h-1.5 w-1.5 shrink-0 rounded-full", tone === "good" ? "bg-emerald-400" : tone === "bad" ? "bg-red-400" : "bg-slate-500")} />
          <span className="leading-relaxed">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function AnalysisCards({ result }: { result: TeamAnalysisResponse }) {
  const a = result.analysis;
  return (
    <div className="space-y-4" data-testid="analysis">
      <Card>
        <CardHeader
          title="Team summary"
          action={
            <div className="flex items-center gap-2">
              <Badge className="bg-slate-500/15 text-slate-300 ring-slate-500/30">Confidence: {a.confidence}</Badge>
              <Badge className={result.generated_by === "openai" ? "bg-brand-soft text-emerald-200 ring-emerald-500/30" : "bg-slate-500/15 text-slate-300 ring-slate-500/30"}>
                {result.generated_by === "openai" ? `AI · ${result.model ?? "OpenAI"}` : "Rule-based"}
              </Badge>
            </div>
          }
        />
        <CardBody>
          <p className="text-sm leading-relaxed text-slate-200">{a.team_summary}</p>
          {a.data_gaps.length ? (
            <div className="mt-3 border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
              <div>
                <p className="font-medium">Data not available</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4">
                  {a.data_gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Strengths" />
          <CardBody><Bullets items={a.strengths} tone="good" /></CardBody>
        </Card>
        <Card>
          <CardHeader title="Weaknesses" />
          <CardBody><Bullets items={a.weaknesses} tone="bad" /></CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Starting lineup" description="Moves based on byes, injuries, eligibility, or a missing projection." />
        <CardBody>
          {a.lineup_changes.length ? (
            <div className="space-y-2">
              {a.lineup_changes.map((c, i) => (
                <div key={i} className="rounded-lg border border-surface-border bg-surface p-3">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <PositionBadge position={c.slot} />
                    <span className="font-medium text-emerald-300">Start {c.start_player}</span>
                    {c.sit_player ? <span className="text-slate-400">over {c.sit_player}</span> : null}
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{c.reason}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No lineup changes recommended.</p>
          )}
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Waiver priorities" />
          <CardBody>
            {a.waiver_priorities.length ? (
              <div className="space-y-2">
                {a.waiver_priorities.map((w, i) => (
                  <div key={i} className="rounded-lg border border-surface-border bg-surface p-3">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <PositionBadge position={w.position} />
                      <span className="font-medium text-slate-100">{w.player_name ?? `Any ${w.position}`}</span>
                      <PriorityBadge priority={w.priority} />
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{w.reason}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400">No waiver moves stand out right now.</p>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Trade strategy" />
          <CardBody className="space-y-3">
            <div>
              <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Can trade away</p>
              <div className="flex flex-wrap gap-1">{a.trade_strategy.can_trade_away.length ? a.trade_strategy.can_trade_away.map((p) => <PositionBadge key={p} position={p} />) : <span className="text-xs text-slate-500">None</span>}</div>
            </div>
            <div>
              <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Should target</p>
              <div className="flex flex-wrap gap-1">{a.trade_strategy.should_target.length ? a.trade_strategy.should_target.map((p) => <PositionBadge key={p} position={p} />) : <span className="text-xs text-slate-500">None</span>}</div>
            </div>
            <p className="text-sm text-slate-300">{a.trade_strategy.reasoning}</p>
          </CardBody>
        </Card>
      </div>

      <Card className="border-brand/30">
        <CardHeader title="This week" description="Do these before kickoff." />
        <CardBody>
          <ol className="space-y-2 text-sm text-slate-200">
            {a.this_week.map((item, i) => (
              <li key={i} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-emerald-200">{i + 1}</span>
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ol>
        </CardBody>
      </Card>

      {result.tools_used.length ? (
        <p className="text-[11px] text-slate-500">Read from: {result.tools_used.join(", ")}</p>
      ) : null}
    </div>
  );
}
