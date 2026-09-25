import { eligibleForSlot } from "@/components/lineup-board";
import { PlayerFace } from "@/components/player-face";
import { PlayerName } from "@/components/player-sheet";
import { PositionBadge } from "@/components/ui/badge";
import type { RankingRow, Rankings, RosterSlot, Team } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { Fragment, useState } from "react";
import { EmptyState } from "./ui/states";

export interface RankMove {
  playerId: string;
  destination: "starter";
  slotIndex: number;
}

function lineLabel(row: RankingRow): string | null {
  if (row.total == null && row.spread == null) return null;
  const total = row.total == null ? "—" : formatLine(row.total);
  const spread = row.spread == null ? "—" : signed(row.spread);
  return `O/U ${total} · ${spread}`;
}

function formatLine(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function signed(value: number): string {
  const text = formatLine(value);
  return value > 0 ? `+${text}` : text;
}

function formatWin(value: number | null): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatValue(value: number | null): string {
  if (value == null) return "—";
  const text = value.toFixed(1);
  return value > 0 ? `+${text}` : text;
}

export function RankingsTable({
  rankings,
  roster,
  pending,
  onMove,
  onAdd,
  emptyTitle = "No rankings",
  emptyDescription = "No projected players are available for this week.",
}: {
  rankings: Rankings;
  roster?: Team | null;
  pending?: boolean;
  onMove?: (move: RankMove) => void;
  onAdd?: (playerId: string) => void;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const owned = roster ? rosterIndex(roster) : new Map<string, Owned>();
  if (!rankings.rows.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className="px-5 py-2 font-medium">#</th>
            <th className="px-2 py-2 font-medium">Player</th>
            <th className="px-2 py-2 font-medium">Opp</th>
            <th className="px-2 py-2 text-right font-medium">Implied</th>
            <th className="px-2 py-2 text-right font-medium">Win</th>
            <th className="px-2 py-2 text-right font-medium">Proj</th>
            <th className="px-2 py-2 text-right font-medium" title="Points scored this season">Pts</th>
            <th className="px-5 py-2 text-right font-medium">Value</th>
            {onMove || onAdd ? <th className="px-5 py-2 font-medium">Move</th> : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">
          {rankings.rows.map((row) => {
            const books = row.books.length ? row.books.join(", ") : "No book posted";
            const line = lineLabel(row);
            const mine = owned.get(row.player_id);
            const yours = row.owned === "you" || Boolean(mine);
            const free = row.owned === null && !mine;
            const choices = roster && mine && onMove ? subChoices(roster, mine) : [];
            const open = openId === row.player_id;
            const columns = onMove || onAdd ? 9 : 8;
            return (
              <Fragment key={row.player_id}>
              <tr className={cn(yours && "bg-emerald-500/15")} data-owned={yours ? "you" : row.owned === "league" ? "league" : "none"}>
                <td className="px-5 py-2.5 tabular-nums text-slate-400">{row.rank}</td>
                <td className="px-2 py-2.5">
                  <div className="flex items-center gap-2">
                    <PlayerFace url={row.headshot_url} name={row.name} size="sm" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <PositionBadge position={row.position} />
                        <PlayerName id={row.player_id} name={row.name} className="font-medium text-slate-100" />
                        {yours ? <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-200">Yours</span> : null}
                      </div>
                      <p className="text-[11px] text-slate-500">{row.nfl_team ?? "FA"}</p>
                    </div>
                  </div>
                </td>
                <td className="px-2 py-2.5 text-xs text-slate-400">
                  {row.opponent ? `${row.home === false ? "@" : "vs"} ${row.opponent}` : "—"}
                </td>
                <td className="px-2 py-2.5 text-right" title={`${books}${line ? `. ${line}` : ""}`}>
                  <div className="tabular-nums text-slate-100">{formatPoints(row.implied_points)}</div>
                  {line ? <div className="text-[11px] text-slate-500">{line}</div> : null}
                </td>
                <td className="px-2 py-2.5 text-right tabular-nums text-slate-300">{formatWin(row.win_probability)}</td>
                <td className="px-2 py-2.5 text-right tabular-nums text-slate-100">{formatPoints(row.projected_points)}</td>
                <td className="px-2 py-2.5 text-right tabular-nums text-slate-200" title="Points scored this season">{formatPoints(row.season_points)}</td>
                <td className="px-5 py-2.5 text-right tabular-nums text-slate-100">{formatValue(row.vorp)}</td>
                {onMove || onAdd ? (
                  <td className="px-5 py-2.5">
                    {free && onAdd ? (
                      <button
                        type="button"
                        data-testid="rank-add"
                        disabled={pending}
                        onClick={() => onAdd(row.player_id)}
                        className="border border-surface-border px-2 py-1 text-xs text-slate-100 hover:border-brand disabled:opacity-50"
                      >
                        Add
                      </button>
                    ) : null}
                    {choices.length ? (
                      <button
                        type="button"
                        data-testid="rank-sub"
                        disabled={pending}
                        aria-expanded={open}
                        onClick={() => setOpenId(open ? null : row.player_id)}
                        className="border border-surface-border px-2 py-1 text-xs text-slate-100 hover:border-brand disabled:opacity-50"
                      >
                        {open ? "Close" : "Sub"}
                      </button>
                    ) : null}
                  </td>
                ) : null}
              </tr>
              {open ? (
                <tr>
                  <td colSpan={columns} className="bg-surface px-5 py-3">
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      {choices.map((choice) => (
                        <button
                          key={`${choice.playerId}-${choice.slotIndex}`}
                          type="button"
                          data-testid="rank-sub-choice"
                          disabled={pending}
                          onClick={() => {
                            if (!onMove) return;
                            setOpenId(null);
                            onMove(choice);
                          }}
                          className="flex items-center gap-2 border border-surface-border bg-surface-raised px-2 py-1.5 text-left text-xs text-slate-100 hover:border-brand disabled:opacity-50"
                        >
                          <PositionBadge position={choice.position} />
                          <PlayerFace url={choice.headshot} name={choice.name} size="sm" />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-medium">{choice.label}</span>
                            <span className="block truncate text-[11px] text-slate-500">{choice.detail}</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface Owned {
  row: RosterSlot;
  where: "starter" | "bench" | "ir";
}

interface SubChoice extends RankMove {
  label: string;
  detail: string;
  name: string;
  position: string | null;
  headshot: string | null;
}

function rosterIndex(team: Team): Map<string, Owned> {
  const map = new Map<string, Owned>();
  for (const row of team.starters) {
    if (row.player) map.set(row.player.id, { row, where: "starter" });
  }
  for (const row of team.bench) {
    if (row.player) map.set(row.player.id, { row, where: "bench" });
  }
  for (const row of team.reserve) {
    if (row.player && row.slot === "IR") map.set(row.player.id, { row, where: "ir" });
  }
  return map;
}

function projLabel(player: RosterSlot["player"]): string {
  if (!player || player.projected_points == null) return "No projection";
  return `${formatPoints(player.projected_points)} proj`;
}

function byProjection(a: RosterSlot, b: RosterSlot): number {
  const left = a.player?.projected_points;
  const right = b.player?.projected_points;
  if (left == null && right == null) return (a.player?.name ?? "").localeCompare(b.player?.name ?? "");
  if (left == null) return 1;
  if (right == null) return -1;
  return right - left || (a.player?.name ?? "").localeCompare(b.player?.name ?? "");
}

function subChoices(team: Team, owned: Owned): SubChoice[] {
  const player = owned.row.player;
  if (!player) return [];
  if (owned.where === "starter" && owned.row.slot_index != null) {
    const slot = team.lineup_slots[owned.row.slot_index] ?? owned.row.slot;
    return [...team.bench, ...team.reserve.filter((row) => row.slot === "IR")]
      .filter((row) => row.player && row.player.id !== player.id && eligibleForSlot(row.player, slot))
      .sort(byProjection)
      .map((row) => ({
        playerId: row.player!.id,
        destination: "starter" as const,
        slotIndex: owned.row.slot_index!,
        label: `Sub in ${row.player!.name}`,
        detail: `${projLabel(row.player)} · replaces ${player.name} (${projLabel(player)})`,
        name: row.player!.name,
        position: row.player!.position,
        headshot: row.player!.headshot_url,
      }));
  }
  return team.lineup_slots.flatMap((slot, index) => {
    if (!eligibleForSlot(player, slot)) return [];
    const occupied = team.starters.find((row) => row.slot_index === index);
    if (occupied?.player?.id === player.id) return [];
    const occupant = occupied?.player;
    return [{
      playerId: player.id,
      destination: "starter" as const,
      slotIndex: index,
      label: occupant ? `Start over ${occupant.name}` : `Start at ${slot}`,
      detail: occupant ? `${projLabel(player)} · ${occupant.name} is ${projLabel(occupant)}` : projLabel(player),
      name: occupant?.name ?? player.name,
      position: occupant?.position ?? player.position,
      headshot: occupant?.headshot_url ?? player.headshot_url,
    }];
  });
}
