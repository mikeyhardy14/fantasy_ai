"use client";

import { opponentLabel, PlayerFace } from "@/components/player-face";
import { PlayerName } from "@/components/player-sheet";
import { SlotBadge } from "@/components/ui/badge";
import type { RosterSlot, Team } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useState, type DragEvent, type ReactNode } from "react";

const SLOT_POSITIONS: Record<string, string[]> = {
  FLEX: ["RB", "WR", "TE"],
  WRRB_FLEX: ["RB", "WR"],
  REC_FLEX: ["WR", "TE"],
  SUPER_FLEX: ["QB", "RB", "WR", "TE"],
  IDP_FLEX: ["DL", "LB", "DB"],
  DST: ["DEF"],
  "D/ST": ["DEF"],
};

export type RosterDestination = "starter" | "bench" | "ir";

export function eligibleForSlot(player: RosterSlot["player"], slot: string) {
  if (!player) return false;
  const positions = new Set(
    player.fantasy_positions.length ? player.fantasy_positions : player.position ? [player.position] : [],
  );
  const allowed = SLOT_POSITIONS[slot] ?? [slot];
  return allowed.some((position) => positions.has(position));
}

export function LineupBoard({
  team,
  irCapacity,
  pending,
  notice,
  onMove,
}: {
  team: Team;
  irCapacity: number;
  pending: boolean;
  notice: string | null;
  onMove: (move: { playerId: string; destination: RosterDestination; slotIndex?: number }) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const irCount = team.reserve.filter((row) => row.slot === "IR" && row.player).length;
  const taxi = team.reserve.filter((row) => row.slot === "TAXI" && row.player);

  function dragId(event: DragEvent) {
    return event.dataTransfer.getData("text/plain");
  }

  function startDrag(event: DragEvent, playerId: string) {
    event.dataTransfer.setData("text/plain", playerId);
    event.dataTransfer.effectAllowed = "move";
  }

  return (
    <div className={cn("divide-y divide-surface-border", pending && "opacity-60")} aria-busy={pending}>
      <ul>
        {team.lineup_slots.map((slot, index) => {
          const filled = team.starters.find((row) => row.slot_index === index) ?? null;
          const key = `slot-${index}`;
          return (
            <li
              key={key}
              data-testid="lineup-slot"
              className={cn("px-4 py-2", over === key && "bg-brand-soft/40")}
              onDragOver={(event) => {
                event.preventDefault();
                setOver(key);
              }}
              onDragLeave={() => setOver((current) => (current === key ? null : current))}
              onDrop={(event) => {
                event.preventDefault();
                setOver(null);
                const playerId = dragId(event);
                if (playerId) onMove({ playerId, destination: "starter", slotIndex: index });
              }}
            >
              <PlayerRow
                slotLabel={slot}
                row={filled}
                points={filled?.points}
                open={!!filled?.player && openId === filled.player.id}
                onToggle={() => filled?.player && setOpenId(openId === filled.player.id ? null : filled.player.id)}
                onDragStart={(event) => filled?.player && startDrag(event, filled.player.id)}
                menu={
                  filled?.player ? (
                    <MoveMenu
                      playerId={filled.player.id}
                      here="starter"
                      team={team}
                      irCapacity={irCapacity}
                      irCount={irCount}
                      onMove={onMove}
                      onClose={() => setOpenId(null)}
                    />
                  ) : null
                }
              />
            </li>
          );
        })}
      </ul>

      <section
        data-testid="bench-drop"
        className={cn("px-0", over === "bench" && "bg-brand-soft/40")}
        onDragOver={(event) => {
          event.preventDefault();
          setOver("bench");
        }}
        onDragLeave={() => setOver((current) => (current === "bench" ? null : current))}
        onDrop={(event) => {
          event.preventDefault();
          setOver(null);
          const playerId = dragId(event);
          if (playerId) onMove({ playerId, destination: "bench" });
        }}
      >
        <h3 className="px-5 pb-1 pt-3 text-[11px] uppercase tracking-wide text-slate-500">Bench</h3>
        {team.bench.length === 0 ? <p className="px-5 py-3 text-xs text-slate-500">Drop a starter here to bench them.</p> : null}
        <ul>
          {team.bench.map((row) => {
            const benchPlayer = row.player;
            if (!benchPlayer) return null;
            return (
              <li key={benchPlayer.id} className="px-4 py-2">
                <PlayerRow
                  slotLabel="BN"
                  row={row}
                  open={openId === benchPlayer.id}
                  onToggle={() => setOpenId(openId === benchPlayer.id ? null : benchPlayer.id)}
                  onDragStart={(event) => startDrag(event, benchPlayer.id)}
                  menu={
                    <MoveMenu
                      playerId={benchPlayer.id}
                      here="bench"
                      team={team}
                      irCapacity={irCapacity}
                      irCount={irCount}
                      onMove={onMove}
                      onClose={() => setOpenId(null)}
                    />
                  }
                />
              </li>
            );
          })}
        </ul>
      </section>

      <section
        data-testid="ir-drop"
        className={cn("px-0", over === "ir" && "bg-brand-soft/40")}
        onDragOver={(event) => {
          event.preventDefault();
          setOver("ir");
        }}
        onDragLeave={() => setOver((current) => (current === "ir" ? null : current))}
        onDrop={(event) => {
          event.preventDefault();
          setOver(null);
          const playerId = dragId(event);
          if (playerId) onMove({ playerId, destination: "ir" });
        }}
      >
        <h3 className="px-5 pb-1 pt-3 text-[11px] uppercase tracking-wide text-slate-500">
          IR{irCapacity > 0 ? ` · ${irCount}/${irCapacity}` : ""}
        </h3>
        {irCapacity <= 0 ? <p className="px-5 py-3 text-xs text-slate-500">This league has no IR slots.</p> : null}
        {irCapacity > 0 && irCount === 0 ? <p className="px-5 py-3 text-xs text-slate-500">Drop a player here for IR.</p> : null}
        <ul>
          {team.reserve
            .filter((row) => row.slot === "IR" && row.player)
            .map((row) => (
              <li key={row.player!.id} className="px-4 py-2">
                <PlayerRow
                  slotLabel="IR"
                  row={row}
                  open={openId === row.player!.id}
                  onToggle={() => setOpenId(openId === row.player!.id ? null : row.player!.id)}
                  onDragStart={(event) => startDrag(event, row.player!.id)}
                  menu={
                    <MoveMenu
                      playerId={row.player!.id}
                      here="ir"
                      team={team}
                      irCapacity={irCapacity}
                      irCount={irCount}
                      onMove={onMove}
                      onClose={() => setOpenId(null)}
                    />
                  }
                />
              </li>
            ))}
        </ul>
        {taxi.length ? (
          <ul className="border-t border-surface-border">
            {taxi.map((row) => (
              <li key={row.player!.id} className="flex items-center gap-2 px-4 py-2 text-xs text-slate-500">
                <SlotBadge slot="TAXI" />
                <span>{row.player!.name}</span>
                <span>Taxi stays put</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      {notice ? <p className="px-5 py-3 text-xs text-slate-400">{notice}</p> : null}
    </div>
  );
}

function PlayerRow({
  slotLabel,
  row,
  points,
  open,
  onToggle,
  onDragStart,
  menu,
}: {
  slotLabel: string;
  row: RosterSlot | null;
  points?: number | null;
  open: boolean;
  onToggle: () => void;
  onDragStart: (event: DragEvent) => void;
  menu: ReactNode;
}) {
  const player = row?.player;
  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <button
          type="button"
          className="rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          aria-label={player ? `Move ${player.name}` : `${slotLabel} slot`}
          aria-expanded={player ? open : undefined}
          onClick={player ? onToggle : undefined}
          disabled={!player}
        >
          <SlotBadge slot={slotLabel} />
        </button>
        {open ? menu : null}
      </div>
      {player ? (
        <>
          <PlayerFace url={player.headshot_url} name={player.name} size="sm" />
          <span draggable onDragStart={onDragStart} className="min-w-0 flex-1 cursor-grab truncate text-sm text-slate-100">
            <PlayerName id={player.id} name={player.name} className="font-medium" />
            <span className="ml-2 text-[11px] text-slate-500">
              {player.nfl_team ?? "FA"}
              {opponentLabel(player) ? ` · ${opponentLabel(player)}` : ""}
            </span>
          </span>
          {points !== undefined ? <span className="w-10 text-right text-xs tabular-nums text-slate-300">{formatPoints(points)}</span> : null}
        </>
      ) : (
        <span className="text-xs text-slate-500">Empty · drop a player here</span>
      )}
    </div>
  );
}

function MoveMenu({
  playerId,
  here,
  team,
  irCapacity,
  irCount,
  onMove,
  onClose,
}: {
  playerId: string;
  here: RosterDestination;
  team: Team;
  irCapacity: number;
  irCount: number;
  onMove: (move: { playerId: string; destination: RosterDestination; slotIndex?: number }) => void;
  onClose: () => void;
}) {
  const player = [...team.starters, ...team.bench, ...team.reserve].find((row) => row.player?.id === playerId)?.player;
  const choices: { label: string; destination: RosterDestination; slotIndex?: number }[] = [];
  if (here !== "bench") choices.push({ label: "Bench", destination: "bench" });
  if (here !== "ir" && irCapacity > 0) {
    choices.push({
      label: irCount >= irCapacity ? "IR full" : "IR",
      destination: "ir",
    });
  }
  team.lineup_slots.forEach((slot, index) => {
    const occupied = team.starters.find((row) => row.slot_index === index);
    if (occupied?.player?.id === playerId) return;
    if (!player || !eligibleForSlot(player, slot)) return;
    const label = occupied?.player ? `Start at ${slot}, replace ${occupied.player.name}` : `Start at ${slot}`;
    choices.push({ label, destination: "starter", slotIndex: index });
  });

  return (
    <>
      <button type="button" className="fixed inset-0 z-10 cursor-default" aria-label="Close move menu" onClick={onClose} />
      <div role="menu" className="absolute left-0 top-full z-20 mt-1 min-w-[12rem] border border-surface-border bg-surface-raised py-1">
        {choices.map((choice) => (
          <button
            key={`${choice.destination}-${choice.slotIndex ?? choice.label}`}
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left text-xs text-slate-100 hover:bg-surface-overlay disabled:text-slate-500"
            disabled={choice.label === "IR full"}
            onClick={() => {
              onClose();
              if (choice.label !== "IR full") onMove({ playerId, destination: choice.destination, slotIndex: choice.slotIndex });
            }}
          >
            {choice.label}
          </button>
        ))}
      </div>
    </>
  );
}
