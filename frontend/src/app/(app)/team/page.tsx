"use client";

import { LineupEditor } from "@/components/lineup-editor";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RosterTable } from "@/components/roster-table";
import { PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useLeagueDetail, useNeeds, useTeam } from "@/lib/queries";
import { cn, formatPoints, GRADE_STYLES } from "@/lib/utils";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function TeamPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <TeamView leagueId={selected.id} currentWeek={selected.current_week} provider={selected.provider} />;
}

function TeamView({ leagueId, currentWeek, provider }: { leagueId: string; currentWeek: number; provider: string }) {
  const [week, setWeek] = useState<number>(currentWeek);
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState<{ text: string; tone: "ok" | "warn" } | null>(null);
  const team = useTeam(leagueId, week);
  const needs = useNeeds(leagueId);
  const detail = useLeagueDetail(leagueId);
  const writesEnabled = !!detail.data?.account.writes_enabled;
  const canEdit = provider === "sleeper" && week === currentWeek && writesEnabled;

  useEffect(() => {
    setEditing(false);
  }, [week, leagueId]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Team"
        description={team.data ? `${team.data.team.name} · ${team.data.team.record} · ${team.data.team.owner_name ?? ""}` : undefined}
        action={
          <Select value={week} onChange={(e) => setWeek(Number(e.target.value))} aria-label="Week">
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>Week {w}{w === currentWeek ? " (current)" : ""}</option>
            ))}
          </Select>
        }
      />

      {provider === "sleeper" && week === currentWeek && detail.data && !writesEnabled ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-100">
          Lineup edits use the token from the Sleeper web app.{" "}
          <Link href="/settings" className="font-medium text-emerald-300 hover:underline">Add it in Settings</Link>
        </div>
      ) : null}

      {notice ? (
        <div
          className={cn(
            "flex gap-3 rounded-xl border p-4 text-sm",
            notice.tone === "ok" ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-100" : "border-amber-500/30 bg-amber-500/5 text-amber-100",
          )}
          role="status"
        >
          {notice.tone === "ok" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
          <p>{notice.text}</p>
        </div>
      ) : null}

      {team.data?.lineup_issues.length ? (
        <div className="flex gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-100" role="alert">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <ul className="space-y-1">
            {team.data.lineup_issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader
              title="Starters"
              description={team.data ? `Projected ${formatPoints(team.data.projected_points)} (${team.data.projection_coverage} coverage)` : undefined}
              action={canEdit && team.data && !editing ? <Button size="sm" onClick={() => { setNotice(null); setEditing(true); }}>Edit lineup</Button> : null}
            />
            {team.isLoading ? <CardBody><SkeletonRows rows={9} /></CardBody> : team.error ? <ErrorState error={team.error} onRetry={() => team.refetch()} /> : editing && team.data ? (
              <LineupEditor
                leagueId={leagueId}
                team={team.data}
                onClose={(next) => {
                  setEditing(false);
                  if (next) setNotice(next);
                }}
              />
            ) : <RosterTable slots={team.data?.starters ?? []} week={week} />}
          </Card>
          <Card>
            <CardHeader title="Bench" />
            {team.isLoading ? <CardBody><SkeletonRows rows={5} /></CardBody> : <RosterTable slots={team.data?.bench ?? []} showPoints={false} emptyLabel="Bench is empty" week={week} />}
          </Card>
          {team.data?.reserve.length ? (
            <Card>
              <CardHeader title="IR / Taxi" />
              <RosterTable slots={team.data.reserve} showPoints={false} week={week} />
            </Card>
          ) : null}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Positional depth" description="Deterministic grades from roster + injuries + byes" />
            <CardBody>
              {needs.isLoading ? (
                <SkeletonRows rows={6} />
              ) : needs.error ? (
                <ErrorState error={needs.error} className="py-4" />
              ) : (
                <ul className="space-y-3">
                  {needs.data?.positions.filter((p) => p.required_starters || p.total_depth).map((p) => (
                    <li key={p.position}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <PositionBadge position={p.position} />
                          <span className={cn("text-sm font-medium", GRADE_STYLES[p.grade])}>{p.grade}</span>
                        </div>
                        <span className="text-xs tabular-nums text-slate-400">
                          {p.healthy_depth}/{p.total_depth} healthy · {p.required_starters} start
                        </span>
                      </div>
                      {p.notes.length ? <p className="mt-1 text-xs text-slate-500">{p.notes[0]}</p> : null}
                    </li>
                  ))}
                </ul>
              )}
              {needs.data ? (
                <p className="mt-4 text-xs text-slate-500">
                  Roster {needs.data.roster_size}/{needs.data.max_roster_size ?? "?"} · {needs.data.open_roster_spots} open spot{needs.data.open_roster_spots === 1 ? "" : "s"}
                </p>
              ) : null}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="League settings" description={detail.data ? `${detail.data.scoring_type ?? "Custom"} · ${detail.data.team_count} teams` : undefined} />
            <CardBody>
              {detail.isLoading ? (
                <SkeletonRows rows={4} />
              ) : detail.data ? (
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Lineup</p>
                    <div className="flex flex-wrap gap-1">
                      {(detail.data.roster_settings.lineup_slots ?? []).map((s, i) => (
                        <PositionBadge key={`${s}${i}`} position={s} />
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Key scoring</p>
                    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                      {Object.entries(detail.data.scoring_settings)
                        .filter(([k]) => ["rec", "pass_td", "rush_td", "rec_td", "pass_yd", "rush_yd", "rec_yd", "pass_int", "fum_lost", "bonus_rec_te"].includes(k))
                        .map(([k, v]) => (
                          <div key={k} className="flex justify-between border-b border-surface-border/40 py-0.5">
                            <dt className="text-slate-400">{k}</dt>
                            <dd className="tabular-nums text-slate-200">{v}</dd>
                          </div>
                        ))}
                    </dl>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Info label="Waivers" value={String(detail.data.league_settings.waiver_type ?? "—")} />
                    <Info label="FAAB budget" value={detail.data.league_settings.waiver_budget ? `$${detail.data.league_settings.waiver_budget}` : "—"} />
                    <Info label="Playoffs start" value={detail.data.league_settings.playoff_week_start ? `Week ${detail.data.league_settings.playoff_week_start}` : "—"} />
                    <Info label="Trade deadline" value={detail.data.league_settings.trade_deadline ? `Week ${detail.data.league_settings.trade_deadline}` : "—"} />
                  </div>
                </div>
              ) : null}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-slate-200">{value}</p>
    </div>
  );
}
