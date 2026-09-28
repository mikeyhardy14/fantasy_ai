"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Team, TeamCompare } from "@/lib/types";
import { formatPoints } from "@/lib/utils";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

export function TeamComparePanel({
  leagueId,
  week,
  teams,
  initialRight,
}: {
  leagueId: string;
  week: number;
  teams: Team[];
  initialRight?: string | null;
}) {
  const yours = teams.find((team) => team.team.is_user_team)?.team.id ?? teams[0]?.team.id ?? "";
  const other = teams.find((team) => team.team.id !== yours)?.team.id ?? "";
  const [left, setLeft] = useState(yours);
  const [right, setRight] = useState(initialRight && initialRight !== yours ? initialRight : other);
  const compare = useMutation({
    mutationFn: () => api.ai.compareTeams(leagueId, { team_ids: [left, right], week }),
  });
  const same = left !== "" && left === right;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Compare" description="Any two teams. The numbers stay next to the write-up." />
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1 text-xs text-slate-400">
            Team
            <Select className="mt-1" aria-label="First team" value={left} onChange={(event) => setLeft(event.target.value)}>
              {teams.map((team) => (
                <option key={team.team.id} value={team.team.id}>
                  {team.team.name}
                </option>
              ))}
            </Select>
          </label>
          <label className="min-w-0 flex-1 text-xs text-slate-400">
            Against
            <Select className="mt-1" aria-label="Second team" value={right} onChange={(event) => setRight(event.target.value)}>
              {teams.map((team) => (
                <option key={team.team.id} value={team.team.id}>
                  {team.team.name}
                </option>
              ))}
            </Select>
          </label>
          <Button type="button" disabled={!left || !right || same} loading={compare.isPending} onClick={() => compare.mutate()}>
            Compare
          </Button>
        </CardBody>
        {same ? <CardBody className="border-t border-surface-border text-sm text-slate-400">Pick two different teams.</CardBody> : null}
        {compare.error ? (
          <CardBody className="border-t border-surface-border text-sm text-red-300">
            {compare.error instanceof Error ? compare.error.message : "Could not compare those teams."}
          </CardBody>
        ) : null}
      </Card>
      {compare.data ? <CompareReadout result={compare.data} /> : null}
    </div>
  );
}

export function CompareReadout({ result }: { result: TeamCompare }) {
  const [left, right] = result.sides;
  const source =
    result.generated_by === "deterministic" ? "From the numbers" : result.generated_by === "gemini" ? "Gemini" : result.generated_by === "groq" ? "Groq" : "OpenAI";
  const positions = [...new Set([...left.positions, ...right.positions].map((row) => row.position))];
  return (
    <div className="space-y-4" data-testid="team-compare">
      <Card>
        <CardHeader title={`Week ${result.week}`} description="Records, scoring, and starter projections." />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-5 py-2 font-medium" />
                <th className="px-3 py-2 font-medium">{left.name}</th>
                <th className="px-5 py-2 font-medium">{right.name}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/60">
              <NumberRow label="Record" left={left.record} right={right.record} />
              <NumberRow label="Points for" left={formatPoints(left.points_for)} right={formatPoints(right.points_for)} />
              <NumberRow label="Points against" left={formatPoints(left.points_against)} right={formatPoints(right.points_against)} />
              <NumberRow label="Week projection" left={formatPoints(left.projected_points)} right={formatPoints(right.projected_points)} />
              <NumberRow label="FAAB" left={left.faab_remaining == null ? "—" : `$${left.faab_remaining}`} right={right.faab_remaining == null ? "—" : `$${right.faab_remaining}`} />
              <NumberRow label="Starters out" left={String(left.starters_out)} right={String(right.starters_out)} />
              <NumberRow label="Starters on bye" left={String(left.starters_on_bye)} right={String(right.starters_on_bye)} />
              {positions.map((position) => {
                const a = left.positions.find((row) => row.position === position);
                const b = right.positions.find((row) => row.position === position);
                return (
                  <NumberRow
                    key={position}
                    label={position}
                    left={positionCell(a)}
                    right={positionCell(b)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <StarterList side={left} />
        <StarterList side={right} />
      </div>
      <Card>
        <CardHeader
          title="Comparison"
          action={<Badge className="bg-brand-soft text-emerald-200 ring-brand/30">{source}</Badge>}
        />
        <CardBody>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200" data-testid="compare-summary">
            {result.summary}
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function positionCell(row: TeamCompare["sides"][number]["positions"][number] | undefined): string {
  if (!row) return "—";
  const projected = row.starter_projection == null ? "No starter projection" : `${formatPoints(row.starter_projection)} proj`;
  return `${row.grade} · ${row.healthy_depth}/${row.total_depth} healthy · ${projected}`;
}

function NumberRow({ label, left, right }: { label: string; left: string; right: string }) {
  return (
    <tr>
      <td className="px-5 py-2 text-slate-500">{label}</td>
      <td className="px-3 py-2 tabular-nums text-slate-100">{left}</td>
      <td className="px-5 py-2 tabular-nums text-slate-100">{right}</td>
    </tr>
  );
}

function StarterList({ side }: { side: TeamCompare["sides"][number] }) {
  return (
    <Card>
      <CardHeader title={`${side.name} starters`} description={side.owner_name ?? undefined} />
      <ul className="divide-y divide-surface-border/60">
        {side.starters.map((starter) => (
          <li key={`${starter.slot}-${starter.name}`} className="flex items-center justify-between gap-3 px-5 py-2 text-sm">
            <span className="min-w-0">
              <span className="text-[11px] uppercase tracking-wide text-slate-500">{starter.slot}</span>
              <span className="mt-0.5 block truncate text-slate-100">{starter.name}</span>
              {starter.injury_status || starter.on_bye ? (
                <span className="block text-[11px] text-amber-200">{starter.on_bye ? "Bye" : starter.injury_status}</span>
              ) : null}
            </span>
            <span className="text-right text-xs text-slate-400">
              <span className="block tabular-nums text-slate-200">Proj {formatPoints(starter.projected_points)}</span>
              <span className="block tabular-nums">{formatPoints(starter.points)} pts</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
