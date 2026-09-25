"use client";

import { Button } from "@/components/ui/button";
import type { Player } from "@/lib/types";
import { useEffect } from "react";

export function ProposeTradeDialog({
  give,
  receive,
  pending,
  error,
  onSend,
  onCancel,
}: {
  give: Player[];
  receive: Player[];
  pending: boolean;
  error: string | null;
  onSend: () => void;
  onCancel: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, pending]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        className="veil-enter absolute inset-0 bg-[#1c1916]/40"
        aria-label="Cancel trade"
        disabled={pending}
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="propose-trade-title"
        className="sheet-enter relative z-10 w-full max-w-lg border border-surface-border bg-surface-raised shadow-card"
      >
        <div className="border-b border-surface-border px-5 py-4">
          <h2 id="propose-trade-title" className="font-serif text-xl text-slate-100">
            Send this offer
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            This goes to one manager in Sleeper. Nothing moves until they accept it.
          </p>
        </div>
        <div className="space-y-3 px-5 py-4 text-sm">
          <p className="text-slate-200">
            <span className="text-slate-500">You give </span>
            {give.map((player) => player.name).join(", ")}
          </p>
          <p className="text-slate-200">
            <span className="text-slate-500">You receive </span>
            {receive.map((player) => player.name).join(", ")}
          </p>
          {error ? <p className="text-sm text-red-300">{error}</p> : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-surface-border px-5 py-3">
          <Button type="button" variant="secondary" data-testid="propose-cancel" disabled={pending} onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" data-testid="propose-send" loading={pending} onClick={onSend}>
            Send offer
          </Button>
        </div>
      </div>
    </div>
  );
}
