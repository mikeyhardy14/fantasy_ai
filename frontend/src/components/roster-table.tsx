import type { RosterSlot } from "@/lib/types";
import { cn, formatPoints, slotHasProblem } from "@/lib/utils";
import { opponentLabel, PlayerFace, SeasonStrip } from "./player-face";
import { PlayerName } from "./player-sheet";
import { FlagBadges, PositionBadge, SlotBadge } from "./ui/badge";

export function RosterTable({
  slots,
  showPoints = true,
  showProjection = true,
  emptyLabel = "No players",
  compact = false,
  week,
}: {
  slots: RosterSlot[];
  showPoints?: boolean;
  showProjection?: boolean;
  emptyLabel?: string;
  compact?: boolean;
  week?: number;
}) {
  if (!slots.length) return <p className="px-5 py-6 text-center text-xs text-slate-500">{emptyLabel}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className="px-5 py-2 font-medium">Slot</th>
            <th className="px-2 py-2 font-medium">Player</th>
            {!compact ? <th className="px-2 py-2 font-medium">Opp</th> : null}
            {showProjection ? <th className="px-2 py-2 text-right font-medium">Proj</th> : null}
            <th className="px-2 py-2 text-right font-medium" title="Points scored this season">Total</th>
            {showPoints ? <th className="px-5 py-2 text-right font-medium">Pts</th> : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">
          {slots.map((s, i) => {
            const p = s.player;
            const problem = slotHasProblem(s);
            return (
              <tr key={`${s.slot}-${p?.id ?? i}`} className={cn("transition hover:bg-surface-overlay/50", problem && "bg-red-500/[0.04]")} data-testid="roster-row">
                <td className="px-5 py-2.5">
                  <SlotBadge slot={s.slot} />
                </td>
                <td className="px-2 py-2.5">
                  {p ? (
                    <div className="flex items-center gap-2">
                      <PlayerFace url={p.headshot_url} name={p.name} size="sm" />
                      <PositionBadge position={p.position} />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <PlayerName
                            id={p.id}
                            name={p.name}
                            className={cn("truncate font-medium text-slate-100", problem && "text-slate-300 line-through decoration-red-400/60")}
                          />
                          <FlagBadges flags={s.flags} injury={p.injury_status ? `${p.injury_status}${p.injury_body_part ? ` (${p.injury_body_part})` : ""}` : null} />
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {p.nfl_team ?? "FA"}
                          {compact && opponentLabel(p, week) ? ` · ${opponentLabel(p, week)}` : ""}
                        </div>
                        {!compact ? <SeasonStrip games={p.schedule} week={week} /> : null}
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs italic text-red-300">Empty slot</span>
                  )}
                </td>
                {!compact ? <td className="px-2 py-2.5 text-xs text-slate-400">{p ? opponentLabel(p, week) ?? "—" : "—"}</td> : null}
                {showProjection ? <td className="px-2 py-2.5 text-right tabular-nums text-slate-300" title={p?.projection_note ?? undefined}>{formatPoints(p?.projected_points)}</td> : null}
                <td className="px-2 py-2.5 text-right tabular-nums text-slate-200" title="Points scored this season">{formatPoints(p?.season_points)}</td>
                {showPoints ? <td className="px-5 py-2.5 text-right tabular-nums font-medium text-slate-100">{formatPoints(s.points)}</td> : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
