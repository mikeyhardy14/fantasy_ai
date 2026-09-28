"use client";

import { NoLeague } from "@/components/no-league";
import { useToast } from "@/components/toast";
import { PageHeader } from "@/components/page-header";
import { PlayerGameLine } from "@/components/player-game";
import { PlayerName } from "@/components/player-sheet";
import { RankingsTable, type RankMove } from "@/components/rankings-table";
import { rosterPlayers, WaiverAddDialog } from "@/components/waiver-add";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { keys, useLeagueDetail, useNeeds, useRankings, useTeam, useWaiverSuggestions } from "@/lib/queries";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { RankingRow } from "@/lib/types";
import { formatPoints } from "@/lib/utils";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
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
  const [lens, setLens] = useState("");
  const [scope, setScope] = useState("");
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [claim, setClaim] = useState<{ id: string; name: string } | null>(null);
  const [claimError, setClaimError] = useState<string | null>(null);
  const toast = useToast();
  const debounced = useDebounced(search);
  const query = debounced.trim().length >= 2 ? debounced.trim() : undefined;
  const narrowing = Boolean(query || team || scope || lens);
  const rankings = useRankings(leagueId, {
    week,
    position: position || undefined,
    q: query,
    team: team || undefined,
    scope: scope || undefined,
    lens: lens || undefined,
  });
  const teamRoster = useTeam(leagueId, week);
  const needs = useNeeds(leagueId);
  const suggestions = useWaiverSuggestions(leagueId, scope === "available");
  const detail = useLeagueDetail(leagueId);
  const qc = useQueryClient();
  const writes = selected?.provider === "sleeper" && !!detail.data?.account.writes_enabled;
  const add = useMutation({
    mutationFn: (dropPlayerId: string | null) => {
      if (!claim) throw new Error("Choose a player to add.");
      return api.leagues.addPlayer(leagueId, claim.id, dropPlayerId ?? undefined);
    },
    onSuccess: async (result) => {
      qc.setQueryData(keys.team(leagueId, week), result.team);
      qc.setQueryData(keys.team(leagueId), result.team);
      setNotice(null);
      setClaim(null);
      setClaimError(null);
      toast(result.message);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error) => {
      setClaimError(error instanceof Error ? error.message : "Could not add that player.");
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
      setNotice(null);
      toast(result.message);
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error) => {
      setNotice(error instanceof Error ? error.message : "Could not make that sub.");
    },
  });
  const shown = rankings.data?.rows.length ?? 0;
  const rosterCount = teamRoster.data
    ? teamRoster.data.starters.length + teamRoster.data.bench.length + teamRoster.data.reserve.length
    : 0;
  const maxSize = needs.data?.max_roster_size ?? null;
  const dropRequired = !teamRoster.data || (maxSize != null && rosterCount >= maxSize);
  const source =
    suggestions.data?.generated_by === "gemini"
      ? "Gemini"
      : suggestions.data?.generated_by === "groq"
        ? "Groq"
        : suggestions.data?.generated_by === "openai"
          ? "OpenAI"
          : "Rule-based";
  const count = rankings.data
    ? rankings.data.truncated
      ? `Showing ${shown}. Search a name to find anyone else.`
      : `${shown} player${shown === 1 ? "" : "s"}`
    : null;

  return (
    <div className="space-y-6">
      <PageHeader title="Players" description="Rankings for the league. Choose Available to add someone, and pick who to drop if the roster is full." />
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
            <Select value={team} onChange={(event) => setTeam(event.target.value)} aria-label="Depth chart">
              <option value="">Depth chart</option>
              {TEAMS.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </Select>
            <Select value={lens} onChange={(event) => setLens(event.target.value)} aria-label="Opportunity">
              <option value="">All workloads</option>
              <option value="carries">Backup RBs, more carries</option>
              <option value="targets">WRs, more targets</option>
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
        {team && rankings.data ? (
          <CardBody className="border-t border-surface-border">
            <DepthChart rows={rankings.data.rows} team={team} />
          </CardBody>
        ) : null}
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
              onAdd={
                writes
                  ? (playerId) => {
                      const row = rankings.data?.rows.find((item) => item.player_id === playerId);
                      setClaimError(null);
                      setClaim({ id: playerId, name: row?.name ?? "this player" });
                    }
                  : undefined
              }
              onTrade={(playerId, side) => router.push(`/trades?${side}=${playerId}`)}
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

      {scope === "available" && suggestions.data ? (
        <Card>
          <CardHeader
            title="Waiver suggestions"
            action={<Badge className="bg-brand-soft text-emerald-200 ring-brand/30">{source}</Badge>}
          />
          <CardBody className="prose prose-invert max-w-none text-sm text-slate-300">
            <ReactMarkdown>{suggestions.data.message}</ReactMarkdown>
          </CardBody>
        </Card>
      ) : null}

      {claim && teamRoster.data ? (
        <WaiverAddDialog
          player={{ name: claim.name }}
          roster={rosterPlayers(teamRoster.data)}
          dropRequired={dropRequired}
          pending={add.isPending}
          error={claimError}
          onCancel={() => {
            setClaim(null);
            setClaimError(null);
          }}
          onDrop={(dropPlayerId) => add.mutate(dropPlayerId)}
          onKeep={dropRequired ? undefined : () => add.mutate(null)}
        />
      ) : null}
    </div>
  );
}

function DepthChart({ rows, team }: { rows: RankingRow[]; team: string }) {
  const groups = ["QB", "RB", "WR", "TE", "K", "DEF"]
    .map((position) => ({
      position,
      players: rows
        .filter((row) => row.position === position)
        .sort((left, right) => (right.projected_points ?? -1) - (left.projected_points ?? -1) || left.name.localeCompare(right.name)),
    }))
    .filter((group) => group.players.length);
  if (!groups.length) return <p className="text-sm text-slate-500">No {team} players in this list.</p>;
  return (
    <div data-testid="depth-chart" className="grid gap-4 sm:grid-cols-2">
      {groups.map((group) => (
        <div key={group.position}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500">{group.position}</p>
          <ul className="mt-1 space-y-1.5">
            {group.players.map((row, index) => (
              <li key={row.player_id} className="text-sm text-slate-200">
                <span className="text-slate-500">{index + 1}. </span>
                <PlayerName id={row.player_id} name={row.name} className="font-medium text-slate-100" />
                <span className="text-slate-400">
                  {row.injury_status ? ` · ${row.injury_status}` : ""}
                  {` · Proj ${formatPoints(row.projected_points)}`}
                </span>
                <PlayerGameLine game={row.game} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
