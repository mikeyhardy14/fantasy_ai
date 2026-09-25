"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export const keys = {
  league: (id: string) => ["league", id] as const,
  team: (id: string, week?: number) => ["league", id, "team", week ?? "current"] as const,
  otherTeam: (id: string, teamId: string, week?: number) => ["league", id, "teams", teamId, week ?? "current"] as const,
  matchup: (id: string, week?: number) => ["league", id, "matchup", week ?? "current"] as const,
  players: (id: string, params: object) => ["league", id, "players", params] as const,
  rankings: (id: string, params: object) => ["league", id, "rankings", params] as const,
  standings: (id: string) => ["league", id, "standings"] as const,
  transactions: (id: string) => ["league", id, "transactions"] as const,
  trades: (id: string) => ["league", id, "trades"] as const,
  needs: (id: string) => ["league", id, "needs"] as const,
  recommendations: (id: string) => ["league", id, "recommendations"] as const,
  waiverSuggestions: (id: string) => ["league", id, "waiver-suggestions"] as const,
  briefing: (id: string) => ["league", id, "briefing"] as const,
};

export function useLeagueDetail(id: string | undefined) {
  return useQuery({ queryKey: keys.league(id!), queryFn: () => api.leagues.get(id!), enabled: !!id });
}

export function useTeam(id: string | undefined, week?: number) {
  return useQuery({ queryKey: keys.team(id!, week), queryFn: () => api.leagues.team(id!, week), enabled: !!id });
}

export function useOtherTeam(id: string | undefined, teamId: string | undefined, week?: number) {
  return useQuery({
    queryKey: keys.otherTeam(id!, teamId!, week),
    queryFn: () => api.leagues.otherTeam(id!, teamId!, week),
    enabled: !!id && !!teamId,
  });
}

export function useMatchup(id: string | undefined, week?: number, refetchInterval?: number | false) {
  return useQuery({
    queryKey: keys.matchup(id!, week),
    queryFn: () => api.leagues.matchup(id!, week),
    enabled: !!id,
    refetchInterval: refetchInterval || undefined,
  });
}

export function usePlayers(id: string | undefined, params: { position?: string; search?: string; available?: boolean; limit?: number }) {
  return useQuery({
    queryKey: keys.players(id!, params),
    queryFn: () => api.leagues.players(id!, params),
    enabled: !!id,
    placeholderData: (prev) => prev,
  });
}

export function useRankings(
  id: string | undefined,
  params: { week?: number; position?: string; q?: string; team?: string; scope?: string },
) {
  return useQuery({
    queryKey: keys.rankings(id!, params),
    queryFn: () => api.leagues.rankings(id!, params),
    enabled: !!id,
    placeholderData: (prev) => prev,
  });
}

export function useStandings(id: string | undefined) {
  return useQuery({ queryKey: keys.standings(id!), queryFn: () => api.leagues.standings(id!), enabled: !!id });
}

export function useTrades(id: string | undefined) {
  return useQuery({ queryKey: keys.trades(id!), queryFn: () => api.leagues.trades(id!), enabled: !!id });
}

export function useTransactions(id: string | undefined) {
  return useQuery({ queryKey: keys.transactions(id!), queryFn: () => api.leagues.transactions(id!), enabled: !!id });
}

export function useNeeds(id: string | undefined) {
  return useQuery({ queryKey: keys.needs(id!), queryFn: () => api.leagues.needs(id!), enabled: !!id });
}

export function useWaiverSuggestions(id: string | undefined) {
  return useQuery({
    queryKey: keys.waiverSuggestions(id!),
    queryFn: () => api.ai.waivers(id!),
    enabled: !!id,
    staleTime: 5 * 60_000,
  });
}

export function useRecommendations(id: string | undefined) {
  return useQuery({ queryKey: keys.recommendations(id!), queryFn: () => api.leagues.recommendations(id!), enabled: !!id });
}

export function useBriefing(id: string | undefined, enabled = true) {
  return useQuery({ queryKey: keys.briefing(id!), queryFn: () => api.leagues.briefing(id!), enabled: !!id && enabled, staleTime: 5 * 60_000 });
}

export function useSyncLeague(id: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.leagues.sync(id!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["league", id] });
      void qc.invalidateQueries({ queryKey: ["leagues"] });
    },
  });
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000, retry: false });
}
