"use client";

import { dehydrate, hydrate, type QueryClient, type DehydratedState } from "@tanstack/react-query";

/** Browser session store so repeat navigations / reloads skip cold API waits. */
const STORAGE_KEY = "omaha_session_db_v1";

const PERSIST_KEYS = new Set(["leagues", "league", "health"]);

function shouldPersist(queryKey: readonly unknown[]): boolean {
  const root = queryKey[0];
  return typeof root === "string" && PERSIST_KEYS.has(root);
}

export function readSessionDb(): DehydratedState | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as DehydratedState;
    if (!parsed || !Array.isArray(parsed.queries)) return undefined;
    return parsed;
  } catch {
    return undefined;
  }
}

export function writeSessionDb(client: QueryClient): void {
  if (typeof window === "undefined") return;
  try {
    const state = dehydrate(client, {
      shouldDehydrateQuery: (query) =>
        query.state.status === "success" && shouldPersist(query.queryKey),
    });
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Quota / private mode — app still works without the session store.
  }
}

export function hydrateSessionDb(client: QueryClient): void {
  const cached = readSessionDb();
  if (cached) hydrate(client, cached);
}

export function clearSessionDb(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
