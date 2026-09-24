import { PlayerFace } from "@/components/player-face";
import { PlayerName } from "@/components/player-sheet";
import { PositionBadge } from "@/components/ui/badge";
import type { RankingRow, Rankings } from "@/lib/types";
import { formatPoints } from "@/lib/utils";
import { EmptyState } from "./ui/states";

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

export function RankingsTable({ rankings }: { rankings: Rankings }) {
  if (!rankings.rows.length) {
    return <EmptyState title="No rankings" description="No projected players are available for this week." />;
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
            <th className="px-5 py-2 text-right font-medium">Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/60">
          {rankings.rows.map((row) => {
            const books = row.books.length ? row.books.join(", ") : "No book posted";
            const line = lineLabel(row);
            return (
              <tr key={row.player_id}>
                <td className="px-5 py-2.5 tabular-nums text-slate-400">{row.rank}</td>
                <td className="px-2 py-2.5">
                  <div className="flex items-center gap-2">
                    <PlayerFace url={row.headshot_url} name={row.name} size="sm" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <PositionBadge position={row.position} />
                        <PlayerName id={row.player_id} name={row.name} className="font-medium text-slate-100" />
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
                <td className="px-5 py-2.5 text-right tabular-nums text-slate-100">{formatValue(row.vorp)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
