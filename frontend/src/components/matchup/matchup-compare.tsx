import { gameForTeam, gameLine } from "@/components/matchup/nfl-slate";
import { opponentLabel, PlayerFace, PlayStatus, playPhase, playRowClass } from "@/components/player/player-face";
import { PlayerName } from "@/components/player/player-sheet";
import { SlotBadge } from "@/components/ui/badge";
import { scoreEdge, slotScore, type SlotScore } from "@/lib/matchup-edge";
import type { NflGame, RosterSlot, SlotCall } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { ArrowLeft, ArrowRight, Minus } from "lucide-react";

export function MatchupCompare({
  week,
  yours,
  theirs,
  yourName,
  theirName,
  calls = [],
  games = [],
  current = true,
  compact = false,
}: {
  week: number;
  yours: RosterSlot[];
  theirs: RosterSlot[];
  yourName: string;
  theirName: string;
  calls?: SlotCall[];
  games?: NflGame[];
  current?: boolean;
  compact?: boolean;
}) {
  const opponentByIndex = new Map(theirs.map((slot) => [slot.slot_index, slot]));
  const rows = yours.map((slot) => {
    const other = slot.slot_index == null ? null : opponentByIndex.get(slot.slot_index) ?? null;
    const left = slotScore(slot, week);
    const right = slotScore(other, week);
    const call = left.live || right.live ? null : calls.find((item) => item.slot_index === slot.slot_index) ?? null;
    return { slot, other, left, right, edge: scoreEdge(left, right), call };
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className={cn("font-medium", compact ? "px-2 py-1.5" : "px-4 py-3")}>Slot</th>
            <th className={cn("font-medium", compact ? "px-2 py-1.5" : "px-4 py-3")}>{yourName}</th>
            <th className={cn("text-center font-medium", compact ? "w-16 px-1 py-1.5" : "w-20 px-2 py-3")}>Edge</th>
            <th className={cn("text-right font-medium", compact ? "px-2 py-1.5" : "px-4 py-3")}>{theirName}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">
          {rows.map((row, index) => {
            const phases = [row.slot, row.other].map((side) => playPhase(gameForTeam(side?.player?.nfl_team, games), side?.player?.position, side?.player?.nfl_team));
            const onNow = phases.some((phase) => phase === "live" || phase === "field");
            const wash = phases.includes("field") ? "field" : phases.includes("live") ? "live" : null;
            return (
            <tr key={`${row.slot.slot}-${row.slot.player?.id ?? index}`} data-testid="matchup-row" className={starterWash(row.slot, row.other, wash)} data-live={onNow ? "true" : "false"} data-phase={wash ?? "none"}>
              <td className={cn(compact ? "px-2 py-1" : "px-4 py-3")}><SlotBadge slot={row.slot.slot} /></td>
              <td className={cn(compact ? "px-2 py-1" : "px-4 py-3")}>
                <PlayerCell slot={row.slot} score={row.left} week={week} games={games} current={current} leading={row.edge != null && row.edge > 0} call={row.call} compact={compact} />
              </td>
              <td className={cn("text-center", compact ? "px-1 py-1" : "px-4 py-3")}>
                <EdgeArrow edge={row.edge} />
              </td>
              <td className={cn(compact ? "px-2 py-1" : "px-4 py-3")}>
                <PlayerCell slot={row.other} score={row.right} week={week} games={games} current={current} align="right" leading={row.edge != null && row.edge < 0} call={row.call} compact={compact} />
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EdgeArrow({ edge }: { edge: number | null }) {
  if (edge == null || edge === 0) {
    return (
      <span className="mx-auto inline-flex h-6 min-w-10 items-center justify-center rounded-full bg-white/5 text-[11px] text-slate-500" aria-label={edge == null ? "No edge" : "Even"}>
        <Minus className="h-3.5 w-3.5" />
      </span>
    );
  }
  const yours = edge > 0;
  const Icon = yours ? ArrowLeft : ArrowRight;
  return (
    <span
      data-testid="edge"
      className={cn(
        "mx-auto inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums",
        yours ? "bg-emerald-400/25 text-emerald-100" : "bg-amber-400/25 text-amber-100",
      )}
      aria-label={yours ? "You are ahead" : "They are ahead"}
    >
      {yours ? <Icon className="h-3.5 w-3.5" aria-hidden /> : null}
      {formatPoints(Math.abs(edge))}
      {yours ? null : <Icon className="h-3.5 w-3.5" aria-hidden />}
    </span>
  );
}

function pointStatus(nfl: NflGame | undefined, score: SlotScore, current: boolean): string | null {
  if (!current) return null;
  if (nfl?.state === "in") return nfl.detail || "Live";
  if (nfl?.state === "post") return "Final";
  return score.live ? "Pts" : "Proj";
}

function PlayerCell({
  slot,
  score,
  week,
  games,
  current,
  leading,
  call,
  align = "left",
  compact = false,
}: {
  slot: RosterSlot | null;
  score: SlotScore;
  week: number;
  games: NflGame[];
  current: boolean;
  leading: boolean;
  call: SlotCall | null;
  align?: "left" | "right";
  compact?: boolean;
}) {
  const player = slot?.player;
  if (!player) return <span className="text-xs italic text-slate-500">Empty</span>;
  const favored = call?.start_name === player.name;
  const nfl = gameForTeam(player.nfl_team, games);
  const onNow = current && nfl?.state === "in";
  const showScore = current && nfl && nfl.state !== "pre";
  const status = pointStatus(nfl, score, current);
  return (
    <div className={cn("flex items-center", compact ? "gap-1.5" : "gap-3", align === "right" && "flex-row-reverse")}>
      <PlayerFace url={player.headshot_url} name={player.name} size={compact ? "xs" : "sm"} />
      <div className={cn("min-w-0 flex-1", align === "right" && "text-right")}>
        <span className={cn("flex flex-wrap items-center gap-1", align === "right" && "justify-end")}>
          <PlayerName id={player.id} name={player.name} className={cn("truncate text-xs font-medium", leading ? "text-slate-100" : "text-slate-300")} />
          <PlayStatus phase={current ? playPhase(nfl, player.position, player.nfl_team) : null} />
        </span>
        {compact ? null : (
          <p className="truncate text-[11px] text-slate-500">
            {player.nfl_team ?? "FA"}
            {opponentLabel(player, week) ? ` · ${opponentLabel(player, week)}` : ""}
            {player.season_points != null ? ` · ${formatPoints(player.season_points)} total` : ""}
          </p>
        )}
        {onNow && slot?.stat_line ? (
          <p className="truncate text-[11px] text-slate-200" data-testid="live-stats">{slot.stat_line}</p>
        ) : null}
        {showScore && nfl && !compact ? (
          <p className={cn("truncate text-[10px]", onNow ? "font-medium text-red-200" : "text-slate-500")} data-testid="nfl-line">
            {gameLine(nfl)}
          </p>
        ) : null}
        {favored && call ? (
          <p className="truncate text-[10px] text-slate-500" data-testid="start-call">
            {Math.round(call.win_prob * 100)}% {call.confidence}
          </p>
        ) : null}
      </div>
      <span className={cn("min-w-10 shrink-0 tabular-nums text-xs", align === "right" ? "text-left" : "text-right", leading ? "font-semibold text-slate-100" : "text-slate-400")}>
        <span className="block">{formatPoints(score.value)}</span>
        {status ? (
          <span
            className={cn(
              "block whitespace-nowrap text-[10px]",
              onNow ? "font-medium text-red-200" : "uppercase tracking-wide text-slate-500",
            )}
            data-testid="point-status"
          >
            {status}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function starterWash(slot: RosterSlot, other: RosterSlot | null, playing: "field" | "live" | null) {
  const flags = [...(slot.flags ?? []), ...(other?.flags ?? [])];
  if (flags.some((flag) => flag === "OUT" || flag === "IR" || flag === "SUSPENDED" || flag === "DOUBTFUL")) return "bg-red-500/10";
  if (playing) return playRowClass(playing);
  if (flags.includes("BYE")) return "bg-slate-500/10";
  return "";
}
