"use client";

import { opponentLabel, PlayerFace } from "@/components/player-face";
import { PlayerName } from "@/components/player-sheet";
import { PositionBadge, SlotBadge } from "@/components/ui/badge";
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

export interface IrRules {
  out?: boolean;
  doubtful?: boolean;
  suspended?: boolean;
  covid?: boolean;
  na?: boolean;
  dnr?: boolean;
}

export function irRulesFromSettings(settings: Record<string, unknown> | undefined): IrRules {
  const on = (key: string) => {
    const value = settings?.[key];
    return value === true || value === 1 || value === "1";
  };
  return {
    out: on("reserve_allow_out"),
    doubtful: on("reserve_allow_doubtful"),
    suspended: on("reserve_allow_sus"),
    covid: on("reserve_allow_cov"),
    na: on("reserve_allow_na"),
    dnr: on("reserve_allow_dnr"),
  };
}

export function eligibleForIr(
  player: { injury_status?: string | null; status?: string | null } | null | undefined,
  rules: IrRules,
): boolean {
  if (!player) return false;
  const label = (player.injury_status || "").trim().toUpperCase();
  const body = (player.status || "").trim().toLowerCase();
  if (label === "IR" || label === "PUP" || body.includes("injured reserve") || body === "pup") return true;
  if ((label === "OUT" || label === "O") && rules.out) return true;
  if ((label === "DOUBTFUL" || label === "D") && rules.doubtful) return true;
  if ((label === "SUS" || label === "SUSPENDED") && rules.suspended) return true;
  if ((label === "COV" || label === "COVID") && rules.covid) return true;
  if ((label === "NA" || label === "NFI") && rules.na) return true;
  if (label === "DNR" && rules.dnr) return true;
  return false;
}

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
  irRules = {},
  pending,
  notice,
  onMove,
  projection = false,
}: {
  team: Team;
  irCapacity: number;
  irRules?: IrRules;
  pending: boolean;
  notice: string | null;
  onMove: (move: { playerId: string; destination: RosterDestination; slotIndex?: number }) => void;
  projection?: boolean;
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
    <div className={cn("divide-y divide-surface-border", pending && "opacity-60", openId && "relative z-30")} aria-busy={pending}>
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
                projection={projection}
                open={openId === (filled?.player?.id ?? `empty-${index}`)}
                onToggle={() => {
                  const id = filled?.player?.id ?? `empty-${index}`;
                  setOpenId(openId === id ? null : id);
                }}
                onDragStart={(event) => filled?.player && startDrag(event, filled.player.id)}
                menu={
                  <MoveMenu
                    playerId={filled?.player?.id ?? ""}
                    here="starter"
                    slotName={slot}
                    slotIndex={index}
                    team={team}
                    irCapacity={irCapacity}
                    irRules={irRules}
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
                  projection={projection}
                  open={openId === benchPlayer.id}
                  onToggle={() => setOpenId(openId === benchPlayer.id ? null : benchPlayer.id)}
                  onDragStart={(event) => startDrag(event, benchPlayer.id)}
                  menu={
                    <MoveMenu
                      playerId={benchPlayer.id}
                      here="bench"
                      team={team}
                      irCapacity={irCapacity}
                      irRules={irRules}
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
          const dragged = [...team.starters, ...team.bench, ...team.reserve].find((row) => row.player?.id === playerId);
          if (playerId && eligibleForIr(dragged?.player, irRules)) onMove({ playerId, destination: "ir" });
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
                  projection={projection}
                  open={openId === row.player!.id}
                  onToggle={() => setOpenId(openId === row.player!.id ? null : row.player!.id)}
                  onDragStart={(event) => startDrag(event, row.player!.id)}
                  menu={
                    <MoveMenu
                      playerId={row.player!.id}
                      here="ir"
                      team={team}
                      irCapacity={irCapacity}
                      irRules={irRules}
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
  projection = false,
  open,
  onToggle,
  onDragStart,
  menu,
}: {
  slotLabel: string;
  row: RosterSlot | null;
  points?: number | null;
  projection?: boolean;
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
          aria-label={player ? `Move ${player.name}` : `Fill ${slotLabel}`}
          aria-expanded={open}
          onClick={onToggle}
          disabled={false}
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
          <span
            className="w-10 text-right text-[10px] uppercase tracking-wide text-slate-500"
            title={projection ? player.projection_note ?? "Projected points this week" : "Points scored this season"}
          >
            <span className="block text-xs normal-case tabular-nums text-slate-300">
              {formatPoints(projection ? player.projected_points : player.season_points)}
            </span>
            {projection ? "proj" : "total"}
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
  slotName,
  slotIndex,
  team,
  irCapacity,
  irRules,
  irCount,
  onMove,
  onClose,
}: {
  playerId: string;
  here: RosterDestination;
  slotName?: string;
  slotIndex?: number;
  team: Team;
  irCapacity: number;
  irRules: IrRules;
  irCount: number;
  onMove: (move: { playerId: string; destination: RosterDestination; slotIndex?: number }) => void;
  onClose: () => void;
}) {
  const player = [...team.starters, ...team.bench, ...team.reserve].find((row) => row.player?.id === playerId)?.player;
  const choices: {
    label: string;
    detail?: string;
    destination: RosterDestination;
    slotIndex?: number;
    slotLabel: string;
    moveId: string;
    face: { name: string; headshot_url: string | null; position: string | null } | null;
    replaced: { name: string; headshot_url: string | null } | null;
  }[] = [];
  if (slotName != null && slotIndex != null) {
    const pool = [...team.bench, ...team.reserve.filter((row) => row.slot === "IR")]
      .filter((row) => row.player && row.player.id !== playerId && eligibleForSlot(row.player, slotName))
      .sort((a, b) => (b.player?.projected_points ?? -Infinity) - (a.player?.projected_points ?? -Infinity) || (a.player?.name ?? "").localeCompare(b.player?.name ?? ""));
    for (const row of pool) {
      const candidate = row.player;
      if (!candidate) continue;
      const projected = candidate.projected_points == null ? "No projection" : `${candidate.projected_points.toFixed(1)} proj`;
      choices.push({
        label: `Sub in ${candidate.name}`,
        detail: projected,
        destination: "starter",
        slotIndex,
        slotLabel: candidate.position ?? slotName,
        moveId: candidate.id,
        face: { name: candidate.name, headshot_url: candidate.headshot_url, position: candidate.position },
        replaced: null,
      });
    }
  }
  if (player && here !== "bench") choices.push({ label: "Bench", destination: "bench", slotLabel: "BN", moveId: playerId, face: null, replaced: null });
  if (player && here !== "ir" && irCapacity > 0 && eligibleForIr(player, irRules)) {
    choices.push({
      label: irCount >= irCapacity ? "IR full" : "IR",
      destination: "ir",
      slotLabel: "IR",
      moveId: playerId,
      face: null,
      replaced: null,
    });
  }
  if (player) {
    team.lineup_slots.forEach((slot, index) => {
      const occupied = team.starters.find((row) => row.slot_index === index);
      if (occupied?.player?.id === playerId) return;
      if (!eligibleForSlot(player, slot)) return;
      const label = occupied?.player ? `Start at ${slot}, replace ${occupied.player.name}` : `Start at ${slot}`;
      choices.push({
        label,
        destination: "starter",
        slotIndex: index,
        slotLabel: slot,
        moveId: playerId,
        face: null,
        replaced: occupied?.player ? { name: occupied.player.name, headshot_url: occupied.player.headshot_url } : null,
      });
    });
  }

  return (
    <>
      <button type="button" className="fixed inset-0 z-10 cursor-default" aria-label="Close move menu" onClick={onClose} />
      <div role="menu" className="menu-enter absolute left-0 top-full z-20 mt-1 min-w-[16rem] border border-surface-border bg-surface-raised py-1 shadow-card">
        {player ? (
          <div className="flex items-center gap-2 border-b border-surface-border px-3 py-2" data-testid="sub-player">
            <PositionBadge position={player.position} />
            <PlayerFace url={player.headshot_url} name={player.name} size="sm" />
            <span className="min-w-0 truncate text-xs font-medium text-slate-100">{player.name}</span>
          </div>
        ) : slotName ? (
          <div className="flex items-center gap-2 border-b border-surface-border px-3 py-2" data-testid="sub-player">
            <SlotBadge slot={slotName} />
            <span className="text-xs font-medium text-slate-100">Choose a sub</span>
          </div>
        ) : null}
        {choices.map((choice) => (
          <button
            key={`${choice.moveId}-${choice.destination}-${choice.slotIndex ?? choice.label}`}
            type="button"
            role="menuitem"
            aria-label={choice.label}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-slate-100 hover:bg-surface-overlay disabled:text-slate-500"
            disabled={choice.label === "IR full"}
            onClick={() => {
              onClose();
              if (choice.label !== "IR full") onMove({ playerId: choice.moveId, destination: choice.destination, slotIndex: choice.slotIndex });
            }}
          >
            {choice.face ? <PositionBadge position={choice.face.position} /> : <SlotBadge slot={choice.slotLabel} />}
            {choice.face ? (
              <>
                <PlayerFace url={choice.face.headshot_url} name={choice.face.name} size="sm" />
                <span className="min-w-0 truncate">{choice.face.name}</span>
              </>
            ) : choice.replaced ? (
              <>
                <PlayerFace url={choice.replaced.headshot_url} name={choice.replaced.name} size="sm" />
                <span className="min-w-0 truncate">{choice.replaced.name}</span>
              </>
            ) : (
              <span>{choice.destination === "starter" ? "Open" : choice.label}</span>
            )}
            {choice.detail ? <span className="ml-auto shrink-0 tabular-nums text-slate-400">{choice.detail}</span> : null}
          </button>
        ))}
      </div>
    </>
  );
}
