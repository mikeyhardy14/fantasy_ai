"use client";

import { PlayerFace } from "@/components/player-face";
import { PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Player, RosterSlot, Team } from "@/lib/types";
import { formatPoints } from "@/lib/utils";
import { useEffect } from "react";

export function rosterPlayers(team: Team): RosterSlot[] {
  const starters = team.starters
    .filter((slot) => slot.player)
    .sort((a, b) => (a.slot_index ?? Number.MAX_SAFE_INTEGER) - (b.slot_index ?? Number.MAX_SAFE_INTEGER));
  const bench = team.bench.filter((slot) => slot.player);
  const reserve = team.reserve
    .filter((slot) => slot.player)
    .sort((a, b) => Number(a.slot !== "IR") - Number(b.slot !== "IR"));
  return [...starters, ...bench, ...reserve];
}

function where(slot: RosterSlot): string {
  if (slot.slot === "IR") return "IR";
  if (slot.slot === "TAXI") return "Taxi";
  if (slot.is_starter) return slot.slot;
  return "Bench";
}

export function WaiverAddDialog({
  player,
  roster,
  dropRequired,
  pending,
  error,
  onDrop,
  onKeep,
  onCancel,
}: {
  player: Player;
  roster: RosterSlot[];
  dropRequired: boolean;
  pending: boolean;
  error: string | null;
  onDrop: (playerId: string) => void;
  onKeep?: () => void;
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
        aria-label="Cancel add"
        disabled={pending}
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="waiver-add-title"
        className="sheet-enter relative z-10 flex max-h-[85vh] w-full max-w-lg flex-col border border-surface-border bg-surface-raised shadow-card"
      >
        <div className="border-b border-surface-border px-5 py-4">
          <h2 id="waiver-add-title" className="font-serif text-xl text-slate-100">
            Add {player.name}
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            {dropRequired
              ? "Your roster is full. Choose who to drop, or cancel."
              : "Choose who to drop, or add them without dropping anyone."}
          </p>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {onKeep ? (
            <button
              type="button"
              data-testid="waiver-keep"
              disabled={pending}
              onClick={onKeep}
              className="mb-2 flex w-full items-center justify-between border border-surface-border bg-surface px-3 py-2 text-left text-sm text-slate-100 hover:border-brand disabled:opacity-50"
            >
              <span className="font-medium">Add without dropping</span>
              <span className="text-xs text-slate-500">Open roster spot</span>
            </button>
          ) : null}
          {roster.length ? (
            <ul className="space-y-1.5">
              {roster.map((slot) => {
                const drop = slot.player!;
                return (
                  <li key={drop.id}>
                    <button
                      type="button"
                      data-testid="waiver-drop"
                      disabled={pending}
                      onClick={() => onDrop(drop.id)}
                      className="flex w-full items-center gap-2 border border-surface-border bg-surface px-3 py-2 text-left text-sm text-slate-100 hover:border-brand disabled:opacity-50"
                    >
                      <PositionBadge position={drop.position} />
                      <PlayerFace url={drop.headshot_url} name={drop.name} size="sm" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">Drop {drop.name}</span>
                        <span className="block truncate text-[11px] text-slate-500">
                          {where(slot)}
                          {drop.injury_status ? ` · ${drop.injury_status}` : ""}
                          {` · ${drop.projected_points == null ? "No projection" : `${formatPoints(drop.projected_points)} proj`}`}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="px-2 py-4 text-sm text-slate-500">Nobody on your roster to drop.</p>
          )}
          {error ? <p className="mt-3 px-2 text-sm text-red-300">{error}</p> : null}
        </div>
        <div className="flex justify-end border-t border-surface-border px-5 py-3">
          <Button type="button" variant="secondary" data-testid="waiver-cancel" disabled={pending} onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
