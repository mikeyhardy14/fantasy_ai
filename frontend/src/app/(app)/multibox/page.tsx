"use client";

import { irRulesFromSettings } from "@/components/lineup-board";
import { LeagueBox, type LineupMove } from "@/components/league-box";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { keys, useLeagueDetail } from "@/lib/queries";
import type { League, Matchup, Team } from "@/lib/types";
import { useMutation, useQueries, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";

const REFRESH_MS = 60_000;

export default function MultiBoxPage() {
  const { leagues, loading, select } = useLeague();
  const teams = useQueries({
    queries: leagues.map((league) => ({
      queryKey: keys.team(league.id, league.current_week),
      queryFn: () => api.leagues.team(league.id, league.current_week),
      refetchInterval: REFRESH_MS,
    })),
  });
  const matchups = useQueries({
    queries: leagues.map((league) => ({
      queryKey: keys.matchup(league.id, league.current_week),
      queryFn: () => api.leagues.matchup(league.id, league.current_week),
      refetchInterval: REFRESH_MS,
    })),
  });

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-80 w-full" />
        ))}
      </div>
    );
  }
  if (!leagues.length) return <NoLeague />;

  const alertCount = teams.reduce((sum, query) => sum + (query.data?.lineup_issues.length ? 1 : 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Multi-Box"
        description={`${leagues.length} league${leagues.length === 1 ? "" : "s"} on one screen. Click a starter to sub, or move players between the lineup, bench, and IR. Scores refresh every minute.${alertCount ? ` ${alertCount} ${alertCount === 1 ? "team needs" : "teams need"} a lineup look.` : ""}`}
      />
      <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
        {leagues.map((league, index) => (
          <MultiBoxLeague
            key={league.id}
            league={league}
            team={teams[index]}
            matchup={matchups[index]}
            onSelect={() => select(league.id)}
          />
        ))}
      </div>
    </div>
  );
}

function MultiBoxLeague({
  league,
  team,
  matchup,
  onSelect,
}: {
  league: League;
  team?: UseQueryResult<Team>;
  matchup?: UseQueryResult<Matchup | null>;
  onSelect: () => void;
}) {
  const detail = useLeagueDetail(league.id);
  const qc = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const writesEnabled = league.provider === "sleeper" && !!detail.data?.account.writes_enabled;
  const reserveSlots = Number(detail.data?.roster_settings?.reserve_slots ?? 0);
  const reservePositions = Array.isArray(detail.data?.roster_settings?.roster_positions)
    ? detail.data.roster_settings.roster_positions.filter((slot) => slot === "IR").length
    : 0;
  const movePlayer = useMutation({
    mutationFn: (move: LineupMove) =>
      api.leagues.movePlayer(league.id, {
        week: team?.data?.week ?? league.current_week,
        player_id: move.playerId,
        destination: move.destination,
        slot_index: move.slotIndex,
      }),
    onSuccess: async (result) => {
      qc.setQueryData(keys.team(league.id, league.current_week), result.team);
      qc.setQueryData(keys.team(league.id), result.team);
      setNotice(result.message);
      await qc.invalidateQueries({ queryKey: ["league", league.id] });
    },
    onError: async (error) => {
      setNotice(error instanceof Error ? error.message : "Could not move that player.");
      await qc.invalidateQueries({ queryKey: keys.team(league.id, league.current_week) });
    },
  });

  return (
    <LeagueBox
      league={league}
      team={team?.data}
      matchup={matchup?.data}
      loading={!!team?.isLoading || !!matchup?.isLoading}
      error={(team?.error ?? matchup?.error) as Error | null}
      onSelect={onSelect}
      canEdit={writesEnabled}
      irCapacity={Math.max(reserveSlots, reservePositions)}
      irRules={irRulesFromSettings(detail.data?.roster_settings)}
      lineupPending={movePlayer.isPending}
      lineupNotice={notice}
      needsToken={league.provider === "sleeper" && !!detail.data && !detail.data.account.writes_enabled}
      onMove={(move) => movePlayer.mutate(move)}
    />
  );
}
