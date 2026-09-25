import { gameForTeam, gameLine } from "@/components/nfl-slate";
import { opponentLabel, PlayerFace } from "@/components/player-face";
import { PlayerName } from "@/components/player-sheet";
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
}: {
  week: number;
  yours: RosterSlot[];
  theirs: RosterSlot[];
  yourName: string;
  theirName: string;
  calls?: SlotCall[];
  games?: NflGame[];
  current?: boolean;
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
            <th className="px-4 py-3 font-medium">Slot</th>
            <th className="px-4 py-3 font-medium">{yourName}</th>
            <th className="w-12 px-4 py-3 text-center font-medium">Edge</th>
            <th className="px-4 py-3 text-right font-medium">{theirName}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">
          {rows.map((row, index) => {
            const onNow = [row.slot, row.other].some((side) => gameForTeam(side?.player?.nfl_team, games)?.state === "in");
            return (
            <tr key={`${row.slot.slot}-${row.slot.player?.id ?? index}`} data-testid="matchup-row" className={cn(onNow && "bg-red-500/10")} data-live={onNow ? "true" : "false"}>
              <td className="px-4 py-3"><SlotBadge slot={row.slot.slot} /></td>
              <td className="px-4 py-3">
                <PlayerCell slot={row.slot} score={row.left} week={week} games={games} current={current} leading={row.edge != null && row.edge > 0} call={row.call} />
              </td>
              <td className="px-4 py-3 text-center">
                <EdgeArrow edge={row.edge} />
              </td>
              <td className="px-4 py-3">
                <PlayerCell slot={row.other} score={row.right} week={week} games={games} current={current} align="right" leading={row.edge != null && row.edge < 0} call={row.call} />
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
    return <Minus className="mx-auto h-4 w-4 text-slate-500" aria-label={edge == null ? "No edge" : "Even"} />;
  }
  const yours = edge > 0;
  const Icon = yours ? ArrowLeft : ArrowRight;
  return <Icon className="mx-auto h-4 w-4 text-slate-100" aria-label={yours ? "You are ahead" : "They are ahead"} />;
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
}: {
  slot: RosterSlot | null;
  score: SlotScore;
  week: number;
  games: NflGame[];
  current: boolean;
  leading: boolean;
  call: SlotCall | null;
  align?: "left" | "right";
}) {
  const player = slot?.player;
  if (!player) return <span className="text-xs italic text-slate-500">Empty</span>;
  const favored = call?.start_name === player.name;
  const nfl = gameForTeam(player.nfl_team, games);
  const onNow = current && nfl?.state === "in";
  const showScore = current && nfl && nfl.state !== "pre";
  const status = pointStatus(nfl, score, current);
  return (
    <div className={cn("flex items-center gap-3", align === "right" && "flex-row-reverse")}>
      <PlayerFace url={player.headshot_url} name={player.name} size="sm" />
      <div className={cn("min-w-0 flex-1", align === "right" && "text-right")}>
        <PlayerName id={player.id} name={player.name} className={cn("block truncate font-medium", leading ? "text-slate-100" : "text-slate-300")} />
        <p className="truncate text-[11px] text-slate-500">
          {player.nfl_team ?? "FA"}
          {opponentLabel(player, week) ? ` · ${opponentLabel(player, week)}` : ""}
          {player.season_points != null ? ` · ${formatPoints(player.season_points)} total` : ""}
        </p>
        {onNow && slot?.stat_line ? (
          <p className="truncate text-[11px] text-slate-200" data-testid="live-stats">{slot.stat_line}</p>
        ) : null}
        {showScore && nfl ? (
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
      <span className={cn("min-w-12 shrink-0 tabular-nums", align === "right" ? "text-left" : "text-right", leading ? "font-semibold text-slate-100" : "text-slate-400")}>
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
