"use client";

import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RankingsTable, type RankMove } from "@/components/rankings-table";
import { Card, CardBody } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { keys, useLeagueDetail, useRankings, useTeam } from "@/lib/queries";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";

const POSITIONS = ["", "QB", "RB", "WR", "TE", "FLEX", "K", "DEF"];
const TEAMS = [
  "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX",
  "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
];

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
  const { selected } = useLeague();
  const [position, setPosition] = useState("");
  const [team, setTeam] = useState("");
  const [scope, setScope] = useState("");
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const debounced = useDebounced(search);
  const query = debounced.trim().length >= 2 ? debounced.trim() : undefined;
  const narrowing = Boolean(query || team || scope);
  const rankings = useRankings(leagueId, {
    week,
    position: position || undefined,
    q: query,
    team: team || undefined,
    scope: scope || undefined,
  });
  const teamRoster = useTeam(leagueId, week);
  const detail = useLeagueDetail(leagueId);
  const qc = useQueryClient();
  const writes = selected?.provider === "sleeper" && !!detail.data?.account.writes_enabled;
  const add = useMutation({
    mutationFn: (playerId: string) => api.leagues.addPlayer(leagueId, playerId),
    onSuccess: async (result) => {
      qc.setQueryData(keys.team(leagueId, week), result.team);
      qc.setQueryData(keys.team(leagueId), result.team);
      setNotice(result.message);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : "Could not add that player.");
    },
  });
  const move = useMutation({
    mutationFn: (choice: RankMove) =>
      api.leagues.movePlayer(leagueId, {
        week,
        player_id: choice.playerId,
        destination: choice.destination,
        slot_index: choice.slotIndex,
      }),
    onSuccess: async (result) => {
      qc.setQueryData(keys.team(leagueId, week), result.team);
      qc.setQueryData(keys.team(leagueId), result.team);
      setNotice(result.message);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : "Could not make that sub.");
    },
  });
  const shown = rankings.data?.rows.length ?? 0;
  const count = rankings.data
    ? rankings.data.truncated
      ? `Showing ${shown}. Search a name to find anyone else.`
      : `${shown} player${shown === 1 ? "" : "s"}`
    : null;

  return (
    <div className="space-y-6">
      <PageHeader title="Players" description="Players you own are highlighted. Add a player nobody else has rostered." />
      <Card>
        <CardBody className="flex flex-col gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <Input
              placeholder="Search players…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="pl-9"
              aria-label="Search players"
            />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <Select value={position} onChange={(event) => setPosition(event.target.value)} aria-label="Position">
              {POSITIONS.map((pos) => (
                <option key={pos || "all"} value={pos}>
                  {pos || "All positions"}
                </option>
              ))}
            </Select>
            <Select value={team} onChange={(event) => setTeam(event.target.value)} aria-label="NFL team">
              <option value="">All teams</option>
              {TEAMS.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </Select>
            <Select value={scope} onChange={(event) => setScope(event.target.value)} aria-label="Roster">
              <option value="">Everyone</option>
              <option value="mine">My roster</option>
              <option value="available">Available</option>
            </Select>
            <p className="text-xs text-slate-500 sm:ml-auto">
              Week {week}
              {count ? ` · ${count}` : ""}
            </p>
          </div>
        </CardBody>
        {notice ? <CardBody className="border-t border-surface-border text-sm text-slate-300">{notice}</CardBody> : null}
        {rankings.isLoading ? (
          <CardBody>
            <SkeletonRows rows={10} />
          </CardBody>
        ) : rankings.error ? (
          <ErrorState error={rankings.error} onRetry={() => rankings.refetch()} />
        ) : rankings.data ? (
          <div className={rankings.isPlaceholderData ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <RankingsTable
              rankings={rankings.data}
              roster={teamRoster.data}
              pending={move.isPending || add.isPending}
              onMove={writes ? (choice) => move.mutate(choice) : undefined}
              onAdd={writes ? (playerId) => add.mutate(playerId) : undefined}
              emptyTitle={narrowing ? "No matches" : "No players"}
              emptyDescription={
                narrowing
                  ? "Try a different name, team, or position."
                  : "No projected players are available for this week."
              }
            />
          </div>
        ) : null}
      </Card>
    </div>
  );
}
