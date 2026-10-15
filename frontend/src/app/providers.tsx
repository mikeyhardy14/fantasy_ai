"use client";

import { AuthProvider } from "@/lib/auth";
import { hydrateSessionDb, writeSessionDb } from "@/lib/session-db";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => {
    const qc = new QueryClient({
      defaultOptions: {
        queries: {
          retry: 1,
          refetchOnWindowFocus: false,
          // Session DB + backend TTL cover freshness; avoid hammering the API.
          staleTime: 60_000,
        },
      },
    });
    hydrateSessionDb(qc);
    return qc;
  });

  useEffect(() => {
    const persist = () => writeSessionDb(client);
    persist();
    return client.getQueryCache().subscribe(() => {
      persist();
    });
  }, [client]);

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
