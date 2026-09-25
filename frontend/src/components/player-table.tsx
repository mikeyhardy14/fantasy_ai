import type { Player } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { opponentLabel, PlayerFace, SeasonStrip } from "./player-face";
import { PlayerName } from "./player-sheet";
import { Badge, PositionBadge } from "./ui/badge";
import { EmptyState } from "./ui/states";

export function PlayerTable({
  players,
  onSelect,
  onAdd,
  addingId,
  selectedIds,
  emptyTitle = "No players found",
  week,
}: {
  players: Player[];
  onSelect?: (player: Player) => void;
  onAdd?: (player: Player) => void;
  addingId?: string | null;
  selectedIds?: Set<string>;
  emptyTitle?: string;
  week?: number;
}) {
  if (!players.length) return <EmptyState title={emptyTitle} description="Try a different position or search term." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className="px-5 py-2 font-medium">Pos</th>
            <th className="px-2 py-2 font-medium">Player</th>
            <th className="px-2 py-2 font-medium">Team</th>
            <th className="px-2 py-2 font-medium">Opp</th>
            <th className="px-2 py-2 font-medium">Status</th>
            <th className="px-2 py-2 text-right font-medium" title="Points scored this season">Pts</th>
            <th className="px-2 py-2 text-right font-medium">Proj</th>
            <th className={cn("py-2 text-right font-medium", onAdd ? "px-2" : "px-5")}>PPG</th>
            {onAdd ? <th className="px-5 py-2 font-medium">Add</th> : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">
          {players.map((p) => {
            const selected = selectedIds?.has(p.id);
            return (
              <tr
                key={p.id}
                className={cn("transition", onSelect && "cursor-pointer hover:bg-surface-overlay/60", selected && "bg-brand-soft/30")}
                onClick={onSelect ? () => onSelect(p) : undefined}
                data-testid="player-row"
              >
                <td className="px-5 py-2.5"><PositionBadge position={p.position} /></td>
                <td className="px-2 py-2.5">
                  <div className="flex items-center gap-2">
                    <PlayerFace url={p.headshot_url} name={p.name} size="sm" />
                    <div className="min-w-0">
                      <PlayerName id={p.id} name={p.name} className="font-medium text-slate-100" />
                      <SeasonStrip games={p.schedule} week={week} />
                    </div>
                  </div>
                </td>
                <td className="px-2 py-2.5 text-slate-400">{p.nfl_team ?? "FA"}</td>
                <td className="px-2 py-2.5 text-xs text-slate-400">{opponentLabel(p, week) ?? "—"}</td>
                <td className="px-2 py-2.5">
                  {p.injury_status ? (
                    <Badge className="bg-amber-500/15 text-amber-200 ring-amber-500/30" title={p.injury_body_part ?? undefined}>{p.injury_status}</Badge>
                  ) : p.on_bye ? (
                    <Badge className="bg-slate-500/20 text-slate-200 ring-slate-400/30">BYE</Badge>
                  ) : (
                    <span className="text-xs text-emerald-300/80">Healthy</span>
                  )}
                </td>
                <td className="px-2 py-2.5 text-right tabular-nums text-slate-200" title="Points scored this season">{formatPoints(p.season_points)}</td>
                <td className="px-2 py-2.5 text-right tabular-nums text-slate-200" title={p.projection_note ?? undefined}>{formatPoints(p.projected_points)}</td>
                <td className={cn("py-2.5 text-right tabular-nums text-slate-400", onAdd ? "px-2" : "px-5")}>{formatPoints(p.points_per_game)}</td>
                {onAdd ? (
                  <td className="px-5 py-2.5">
                    <button
                      type="button"
                      data-testid="waiver-add"
                      disabled={addingId === p.id}
                      onClick={(event) => {
                        event.stopPropagation();
                        onAdd(p);
                      }}
                      className="border border-surface-border px-2 py-1 text-xs text-slate-100 hover:border-brand disabled:opacity-50"
                    >
                      Add
                    </button>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
