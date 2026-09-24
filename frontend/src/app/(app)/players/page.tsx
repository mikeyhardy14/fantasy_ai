"use client";

import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { PlayerTable } from "@/components/player-table";
import { Card, CardBody } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { usePlayers } from "@/lib/queries";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";

const POSITIONS = ["", "QB", "RB", "WR", "TE", "K", "DEF"];

export default function PlayersPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <PlayersView leagueId={selected.id} week={selected.current_week} />;
}

function useDebounced<T>(value: T, delay = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

function PlayersView({ leagueId, week }: { leagueId: string; week: number }) {
  const [position, setPosition] = useState("");
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState<"available" | "all">("available");
  const debounced = useDebounced(search);
  const players = usePlayers(leagueId, {
    position: position || undefined,
    search: debounced.length >= 2 ? debounced : undefined,
    available: scope === "available",
    limit: 100,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Players" description="Search the league player pool. Available = not on any roster." />
      <Card>
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <Input placeholder="Search players…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" aria-label="Search players" />
          </div>
          <Select value={position} onChange={(e) => setPosition(e.target.value)} aria-label="Position">
            {POSITIONS.map((p) => (
              <option key={p} value={p}>{p || "All positions"}</option>
            ))}
          </Select>
          <Select value={scope} onChange={(e) => setScope(e.target.value as "available" | "all")} aria-label="Scope">
            <option value="available">Available only</option>
            <option value="all">All players</option>
          </Select>
        </CardBody>
        {players.isLoading ? (
          <CardBody><SkeletonRows rows={10} /></CardBody>
        ) : players.error ? (
          <ErrorState error={players.error} onRetry={() => players.refetch()} />
        ) : (
          <PlayerTable players={players.data ?? []} week={week} />
        )}
      </Card>
    </div>
  );
}
