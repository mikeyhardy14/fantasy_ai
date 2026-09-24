"use client";

import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RankingsTable } from "@/components/rankings-table";
import { Card, CardBody } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useRankings } from "@/lib/queries";
import { useState } from "react";

const POSITIONS = ["", "QB", "RB", "WR", "TE", "K", "DEF"];

export default function RankingsPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <RankingsView leagueId={selected.id} week={selected.current_week} />;
}

function RankingsView({ leagueId, week }: { leagueId: string; week: number }) {
  const [position, setPosition] = useState("");
  const rankings = useRankings(leagueId, { week, position: position || undefined });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rankings"
        description="Weekly value from DraftKings prop lines, scored with this league's settings."
      />
      <Card>
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Select value={position} onChange={(event) => setPosition(event.target.value)} aria-label="Position">
            {POSITIONS.map((pos) => (
              <option key={pos || "all"} value={pos}>
                {pos || "All positions"}
              </option>
            ))}
          </Select>
          <p className="text-xs text-slate-500">Week {week}</p>
        </CardBody>
        {rankings.data?.notes.length ? (
          <CardBody className="border-t border-surface-border">
            <ul className="space-y-1.5 text-sm text-slate-400">
              {rankings.data.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </CardBody>
        ) : null}
        {rankings.isLoading ? (
          <CardBody>
            <SkeletonRows rows={10} />
          </CardBody>
        ) : rankings.error ? (
          <ErrorState error={rankings.error} onRetry={() => rankings.refetch()} />
        ) : rankings.data ? (
          <RankingsTable rankings={rankings.data} />
        ) : null}
      </Card>
    </div>
  );
}
