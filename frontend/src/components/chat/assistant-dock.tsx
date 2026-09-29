"use client";

import { Chat } from "@/components/chat/chat";
import { cn } from "@/lib/utils";
import { Maximize2, Minimize2, Sparkles, X } from "lucide-react";
import { useState } from "react";

type DockSize = "closed" | "small" | "large";

export function AssistantDock({ leagueId, aiEnabled }: { leagueId: string; aiEnabled: boolean | undefined }) {
  const [size, setSize] = useState<DockSize>("closed");

  if (size === "closed") {
    return (
      <button
        type="button"
        data-testid="assistant-dock"
        data-size="closed"
        className="fixed bottom-4 right-4 z-40 inline-flex items-center gap-2 rounded-full bg-brand px-4 py-3 text-sm font-medium text-slate-950 shadow-lg hover:bg-emerald-500"
        onClick={() => setSize("small")}
      >
        <Sparkles className="h-4 w-4" aria-hidden />
        Assistant
      </button>
    );
  }

  return (
    <section
      data-testid="assistant-dock"
      data-size={size}
      className={cn(
        "fixed z-40 flex flex-col overflow-hidden rounded-xl border border-white/10 bg-surface-raised shadow-xl",
        size === "large"
          ? "inset-x-3 bottom-3 top-20 sm:inset-auto sm:bottom-4 sm:right-4 sm:h-[min(40rem,calc(100vh-2rem))] sm:w-[min(44rem,calc(100vw-2rem))]"
          : "bottom-4 right-4 h-[28rem] w-[min(22rem,calc(100vw-2rem))]",
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
        <p className="text-sm font-medium text-slate-100">Assistant</p>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="rounded-md p-1.5 text-slate-300 hover:bg-white/5 hover:text-slate-100"
            aria-label={size === "large" ? "Shrink assistant" : "Enlarge assistant"}
            onClick={() => setSize(size === "large" ? "small" : "large")}
          >
            {size === "large" ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </button>
          <button
            type="button"
            className="rounded-md p-1.5 text-slate-300 hover:bg-white/5 hover:text-slate-100"
            aria-label="Minimize assistant"
            onClick={() => setSize("closed")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        <Chat leagueId={leagueId} aiEnabled={aiEnabled} dock />
      </div>
    </section>
  );
}
