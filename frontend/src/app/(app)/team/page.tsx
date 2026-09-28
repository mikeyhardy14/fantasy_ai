"use client";

import { irRulesFromSettings, LineupBoard } from "@/components/lineup-board";
import { LineupEditor } from "@/components/lineup-editor";
import { useToast } from "@/components/toast";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RosterTable } from "@/components/roster-table";
import { PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { keys, useLeagueDetail, useLineupManagement, useNeeds, useTeam } from "@/lib/queries";
import { cn, formatPoints, GRADE_STYLES } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
  const toast = useToast();
  const team = useTeam(leagueId, week);
  const needs = useNeeds(leagueId);
  const detail = useLeagueDetail(leagueId);
  const writesEnabled = !!detail.data?.account.writes_enabled;
  const canEdit = provider === "sleeper" && week === currentWeek && writesEnabled;
  const management = useLineupManagement(provider === "sleeper" ? leagueId : undefined);
  const queryClient = useQueryClient();
  const reserveSlots = Number(detail.data?.roster_settings?.reserve_slots ?? 0);
  const reservePositions = Array.isArray(detail.data?.roster_settings?.roster_positions)
    ? (detail.data.roster_settings.roster_positions as string[]).filter((slot) => slot === "IR").length
    : 0;
  const movePlayer = useMutation({
    mutationFn: (move: { playerId: string; destination: "starter" | "bench" | "ir"; slotIndex?: number }) =>
      api.leagues.movePlayer(leagueId, {
        week,
        player_id: move.playerId,
        destination: move.destination,
        slot_index: move.slotIndex,
      }),
    onSuccess: async (result) => {
      queryClient.setQueryData(keys.team(leagueId, week), result.team);
      queryClient.setQueryData(keys.team(leagueId), result.team);
      setNotice(null);
      toast(result.message);
      await queryClient.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error) => {
      setNotice({ text: error instanceof Error ? error.message : "Could not move that player.", tone: "warn" });
    },
  });
  const saveManagement = useMutation({
    mutationFn: (enabled: boolean) => api.leagues.saveManagement(leagueId, enabled),
    onSuccess: (result) => queryClient.setQueryData(keys.management(leagueId), result),
  });

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

      {provider === "sleeper" ? (
        <Card data-testid="ai-management">
          <CardHeader title="AI Management" description="Subs a starter who cannot play, and activates a player on IR who can." />
          <CardBody>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                data-testid="ai-management-toggle"
                checked={management.data?.enabled ?? false}
                disabled={!management.data?.available || saveManagement.isPending}
                onChange={(event) => saveManagement.mutate(event.target.checked)}
              />
              <span>
                <span className="font-medium text-slate-100">Manage this lineup</span>
                <span className="mt-1 block text-xs leading-relaxed text-slate-400">
                  If a starter is out, doubtful, suspended, or on bye, someone who can play takes that spot. A player on IR who can play is activated into that spot, or onto the bench. A questionable starter stays.
                </span>
              </span>
            </label>
            {management.data && !management.data.available ? (
              <p className="mt-3 text-xs text-amber-200">Save your Sleeper token in Settings. Moves are written to this week&apos;s lineup.</p>
            ) : null}
            {saveManagement.error ? <p className="mt-3 text-sm text-red-300">{saveManagement.error.message}</p> : null}
          </CardBody>
        </Card>
      ) : null}

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
              title="Lineup"
              description={
                canEdit
                  ? "Tap Swap, then the player who should take that spot. One more tap sends it."
                  : team.data
                    ? `Projected ${formatPoints(team.data.projected_points)} (${team.data.projection_coverage} coverage)`
                    : undefined
              }
              action={
                canEdit && team.data && !editing ? (
                  <Button size="sm" variant="secondary" onClick={() => { setNotice(null); setEditing(true); }}>
                    Set every slot
                  </Button>
                ) : null
              }
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
            ) : canEdit && team.data ? (
              <LineupBoard
                team={team.data}
                irCapacity={Math.max(reserveSlots, reservePositions)}
                irRules={irRulesFromSettings(detail.data?.roster_settings)}
                pending={movePlayer.isPending}
                notice={null}
                projection
                quick
                showGame
                onMove={(move) => movePlayer.mutate(move)}
              />
            ) : (
              <>
                <RosterTable slots={team.data?.starters ?? []} week={week} />
                <div className="border-t border-surface-border">
                  <p className="px-5 pt-3 text-[11px] uppercase tracking-wide text-slate-500">Bench</p>
                  <RosterTable slots={team.data?.bench ?? []} emptyLabel="Bench is empty" week={week} />
                </div>
                {team.data?.reserve.length ? (
                  <div className="border-t border-surface-border">
                    <p className="px-5 pt-3 text-[11px] uppercase tracking-wide text-slate-500">IR / Taxi</p>
                    <RosterTable slots={team.data.reserve} week={week} />
                  </div>
                ) : null}
              </>
            )}
          </Card>
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
