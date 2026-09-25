"use client";

import { PlayerSheetProvider } from "@/components/player-sheet";
import { Sidebar } from "@/components/sidebar";
import { Skeleton } from "@/components/ui/states";
import { useAuth } from "@/lib/auth";
import { LeagueProvider } from "@/lib/league";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen">
        <div className="hidden w-64 border-r border-surface-border bg-surface-raised p-4 lg:block">
          <Skeleton className="h-8 w-32" />
          <div className="mt-8 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        </div>
        <main className="flex-1 p-8">
          <Skeleton className="h-6 w-48" />
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
        </main>
      </div>
    );
  }

  return (
    <LeagueProvider>
      <PlayerSheetProvider>
      <div className="flex min-h-screen flex-col lg:flex-row">
        <Sidebar />
        <main className="flex-1 min-w-0">
          <div className="page-enter mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10 lg:py-10">{children}</div>
        </main>
      </div>
      </PlayerSheetProvider>
    </LeagueProvider>
  );
}
