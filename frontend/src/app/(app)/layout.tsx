"use client";

import { PlayerDirectory } from "@/components/player/player-mentions";
import { PlayerSheetProvider } from "@/components/player/player-sheet";
import { Sidebar } from "@/components/shell/sidebar";
import { ToastProvider } from "@/components/shell/toast";
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
      <div className="flex min-h-screen flex-col lg:flex-row">
        <div className="hidden w-64 shrink-0 border-r border-surface-border bg-surface-raised p-4 lg:block">
          <Skeleton className="h-8 w-32" />
          <div className="mt-8 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        </div>
        <main className="min-w-0 flex-1">
          <div className="mx-auto max-w-none px-3 py-3 sm:px-4 lg:px-6">
            <Skeleton className="h-7 w-64" />
            <div className="mt-2 grid gap-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-72 w-full" />
              ))}
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <LeagueProvider>
      <ToastProvider>
        <PlayerDirectory>
        <PlayerSheetProvider>
          <div className="flex min-h-screen flex-col lg:flex-row">
            <Sidebar />
            <main className="min-w-0 flex-1">{children}</main>
          </div>
        </PlayerSheetProvider>
        </PlayerDirectory>
      </ToastProvider>
    </LeagueProvider>
  );
}
