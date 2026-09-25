"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import type { League } from "./types";

const STORAGE_KEY = "fantasy_ai_selected_league";

interface LeagueState {
  leagues: League[];
  loading: boolean;
  error: Error | null;
  selected: League | null;
  select: (id: string) => void;
  refetch: () => void;
}

const LeagueContext = createContext<LeagueState | null>(null);

export function LeagueProvider({ children }: { children: ReactNode }) {
  const query = useQuery({ queryKey: ["leagues"], queryFn: api.leagues.list, refetchInterval: 15_000 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedId(window.localStorage.getItem(STORAGE_KEY));
  }, []);

  const leagues = query.data ?? [];
  const selected = useMemo(() => {
    if (!leagues.length) return null;
    return leagues.find((l) => l.id === selectedId) ?? leagues[0];
  }, [leagues, selectedId]);

  useEffect(() => {
    if (selected && selected.id !== selectedId) {
      setSelectedId(selected.id);
      window.localStorage.setItem(STORAGE_KEY, selected.id);
    }
  }, [selected, selectedId]);

  const value = useMemo<LeagueState>(
    () => ({
      leagues,
      loading: query.isLoading,
      error: (query.error as Error) ?? null,
      selected,
      select: (id) => {
        setSelectedId(id);
        window.localStorage.setItem(STORAGE_KEY, id);
      },
      refetch: () => void query.refetch(),
    }),
    [leagues, query, selected],
  );

  return <LeagueContext.Provider value={value}>{children}</LeagueContext.Provider>;
}

export function useLeague(): LeagueState {
  const ctx = useContext(LeagueContext);
  if (!ctx) throw new Error("useLeague must be used within LeagueProvider");
  return ctx;
}
