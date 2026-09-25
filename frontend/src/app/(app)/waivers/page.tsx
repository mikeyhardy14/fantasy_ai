"use client";

import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { PlayerTable } from "@/components/player-table";
import { Badge, PositionBadge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useNeeds, usePlayers, useTeam, useWaiverSuggestions } from "@/lib/queries";
import type { Player } from "@/lib/types";
import { cn, GRADE_STYLES } from "@/lib/utils";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

export default function WaiversPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <WaiversView leagueId={selected.id} week={selected.current_week} />;
}

function byProjection(players: Player[]): Player[] {
  return [...players].sort((a, b) => {
    if (a.projected_points == null && b.projected_points == null) return a.name.localeCompare(b.name);
    if (a.projected_points == null) return 1;
    if (b.projected_points == null) return -1;
    return b.projected_points - a.projected_points;
  });
}

function WaiversView({ leagueId, week }: { leagueId: string; week: number }) {
  const needs = useNeeds(leagueId);
  const team = useTeam(leagueId);
  const suggestions = useWaiverSuggestions(leagueId);
  // null follows the weakest position. "" is an explicit All.
  const [position, setPosition] = useState<string | null>(null);
  const showingAll = position === "";
  const weakest = needs.data?.weakest_positions[0] ?? "";
  const effectivePosition = showingAll ? "" : (position ?? weakest);
  const available = usePlayers(leagueId, { position: effectivePosition || undefined, available: true, limit: 40 });

  const source = suggestions.data?.generated_by === "gemini" ? "Gemini" : suggestions.data?.generated_by === "groq" ? "Groq" : suggestions.data?.generated_by === "openai" ? "OpenAI" : "Rule-based";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Waivers"
        description={
          team.data
            ? `${team.data.team.faab_remaining !== null ? `$${team.data.team.faab_remaining} FAAB remaining` : "Waiver priority"}${team.data.team.waiver_position ? ` · priority #${team.data.team.waiver_position}` : ""}`
            : undefined
        }
      />
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader
              title="Available players"
              description={
                showingAll || !effectivePosition
                  ? "All positions, highest projected first"
                  : `Highest projected ${effectivePosition}${position === null ? ", your weakest position" : ""}`
              }
              action={
                <div className="flex flex-wrap gap-1">
                  {["", "QB", "RB", "WR", "TE", "K", "DEF"].map((p) => (
                    <button
                      key={p}
                      onClick={() => setPosition(p)}
                      className={cn(
                        "rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset transition",
                        (showingAll ? p === "" : p === effectivePosition)
                          ? "bg-brand-soft text-emerald-200 ring-emerald-500/40"
                          : "text-slate-400 ring-surface-border hover:text-slate-100",
                      )}
                    >
                      {p || "All"}
                    </button>
                  ))}
                </div>
              }
            />
            {available.isLoading ? <CardBody><SkeletonRows rows={8} /></CardBody> : available.error ? <ErrorState error={available.error} onRetry={() => available.refetch()} /> : <PlayerTable players={byProjection(available.data ?? [])} emptyTitle={showingAll ? "No available players" : "No available players at this position"} week={week} />}
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Roster needs" />
            <CardBody>
              {needs.isLoading ? (
                <SkeletonRows rows={5} />
              ) : needs.data ? (
                <div className="space-y-3">
                  <div>
                    <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Target</p>
                    <div className="flex flex-wrap gap-1">{needs.data.weakest_positions.length ? needs.data.weakest_positions.map((p) => <PositionBadge key={p} position={p} />) : <span className="text-xs text-slate-500">No weak positions</span>}</div>
                  </div>
                  <ul className="space-y-1.5">
                    {needs.data.positions.filter((p) => p.required_starters || p.total_depth).map((p) => (
                      <li key={p.position} className="flex items-center justify-between text-sm">
                        <span className="flex items-center gap-2"><PositionBadge position={p.position} /><span className={GRADE_STYLES[p.grade]}>{p.grade}</span></span>
                        <span className="text-xs text-slate-500">{p.healthy_depth} healthy</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-slate-500">{needs.data.open_roster_spots} open roster spot{needs.data.open_roster_spots === 1 ? "" : "s"}</p>
                </div>
              ) : null}
            </CardBody>
          </Card>
          <Card>
            <CardHeader
              title="Suggestions"
              action={suggestions.data ? <Badge className="bg-brand-soft text-emerald-200 ring-emerald-500/30">{source}</Badge> : null}
            />
            <CardBody>
              {suggestions.isLoading ? (
                <div className="space-y-3">
                  <SkeletonRows rows={4} />
                  <p className="text-xs text-slate-500">Checking the waiver wire…</p>
                </div>
              ) : suggestions.error ? (
                <ErrorState error={suggestions.error} onRetry={() => suggestions.refetch()} className="py-4" />
              ) : (
                <div className="prose-chat text-sm text-slate-200">
                  <ReactMarkdown>{suggestions.data?.message ?? ""}</ReactMarkdown>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
