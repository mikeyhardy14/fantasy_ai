"use client";

import { Button } from "@/components/ui/button";
import { SlotBadge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Player, Team } from "@/lib/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const SLOT_POSITIONS: Record<string, string[]> = {
  FLEX: ["RB", "WR", "TE"],
  WRRB_FLEX: ["RB", "WR"],
  REC_FLEX: ["WR", "TE"],
  SUPER_FLEX: ["QB", "RB", "WR", "TE"],
  IDP_FLEX: ["DL", "LB", "DB"],
  DST: ["DEF"],
  "D/ST": ["DEF"],
};

function eligible(player: Player, slot: string) {
  const positions = new Set(
    player.fantasy_positions.length ? player.fantasy_positions : player.position ? [player.position] : [],
  );
  const allowed = SLOT_POSITIONS[slot] ?? [slot];
  return allowed.some((position) => positions.has(position));
}

export function LineupEditor({
  leagueId,
  team,
  onClose,
}: {
  leagueId: string;
  team: Team;
  onClose: (notice?: { text: string; tone: "ok" | "warn" }) => void;
}) {
  const players = useMemo(() => {
    const seen = new Set<string>();
    const rows: Player[] = [];
    for (const slot of [...team.starters, ...team.bench]) {
      if (!slot.player || slot.slot === "IR" || slot.slot === "TAXI" || seen.has(slot.player.id)) continue;
      seen.add(slot.player.id);
      rows.push(slot.player);
    }
    return rows;
  }, [team]);
  const [picks, setPicks] = useState<string[]>(() =>
    team.lineup_slots.map((_, index) => team.starters.find((slot) => slot.slot_index === index)?.player?.id ?? ""),
  );
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api.leagues.setLineup(
        leagueId,
        team.week,
        picks.map((id) => id || null),
      ),
    onSuccess: async (result) => {
      await qc.invalidateQueries({ queryKey: ["league", leagueId] });
      const confirmed = result.verified === true && result.public_api_confirmed === true;
      onClose({ text: result.message, tone: confirmed ? "ok" : "warn" });
    },
  });
  const duplicate = useMemo(() => {
    const ids = picks.filter(Boolean);
    return new Set(ids).size !== ids.length;
  }, [picks]);

  return (
    <div className="divide-y divide-surface-border/60">
      {team.lineup_slots.map((slot, index) => {
        const taken = new Set(picks.filter((id, pickIndex) => id && pickIndex !== index));
        const options = players.filter((player) => picks[index] === player.id || (!taken.has(player.id) && eligible(player, slot)));
        return (
          <div key={`${slot}-${index}`} className="flex items-center gap-3 px-5 py-2.5">
            <SlotBadge slot={slot} />
            <Select
              className="min-w-0 flex-1"
              aria-label={`${slot} starter`}
              value={picks[index]}
              onChange={(event) => {
                const next = picks.slice();
                next[index] = event.target.value;
                setPicks(next);
              }}
            >
              <option value="">Empty</option>
              {options.map((player) => (
                <option key={player.id} value={player.id}>
                  {player.name} · {player.position ?? "?"}
                  {player.nfl_team ? ` · ${player.nfl_team}` : ""}
                </option>
              ))}
            </Select>
          </div>
        );
      })}
      <div className="space-y-3 px-5 py-3">
        <p className="text-xs text-slate-500">
          This updates the lineup Sleeper scores for week {team.week}, then re-reads it. The public roster API can lag behind that result.
        </p>
        {duplicate ? <p className="text-xs text-amber-200">A player is in more than one slot.</p> : null}
        {save.error ? <p className="text-xs text-red-300">{save.error instanceof Error ? save.error.message : "Could not save the lineup."}</p> : null}
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => onClose()} disabled={save.isPending}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => save.mutate()} loading={save.isPending} disabled={duplicate}>
            Save lineup
          </Button>
        </div>
      </div>
    </div>
  );
}
