import { PlayerFace } from "@/components/player-face";
import type { Transaction, TransactionPlayer } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

export function TransactionList({ txs }: { txs: Transaction[] }) {
  return (
    <ul className="divide-y divide-surface-border/60">
      {txs.map((tx) => (
        <li key={tx.id} className={cn("px-5 py-3 text-xs", tx.involves_user && "bg-brand-soft/10")} data-testid="transaction">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium uppercase tracking-wide text-slate-400">
              {tx.type.replaceAll("_", " ")}
              {tx.faab_bid ? ` · $${tx.faab_bid}` : ""}
            </span>
            <span className="text-slate-500">{tx.week ? `Wk ${tx.week}` : relativeTime(tx.created_at)}</span>
          </div>
          {tx.type === "trade" ? <TradeBody tx={tx} /> : <Moves tx={tx} />}
        </li>
      ))}
    </ul>
  );
}

function Moves({ tx }: { tx: Transaction }) {
  if (!tx.adds.length && !tx.drops.length) return <p className="mt-2 text-slate-500">{tx.team_names.join(" ↔ ")}</p>;
  return (
    <div className="mt-2 space-y-2">
      {tx.adds.map((player, index) => (
        <Move key={`add-${player.player_id ?? index}`} player={player} direction="to" />
      ))}
      {tx.drops.map((player, index) => (
        <Move key={`drop-${player.player_id ?? index}`} player={player} direction="from" />
      ))}
    </div>
  );
}

function Move({ player, direction }: { player: TransactionPlayer; direction: "to" | "from" }) {
  const name = player.player_name ?? "Unknown";
  const added = direction === "to";
  return (
    <div className="flex items-center gap-2" data-testid="tx-player">
      <PlayerFace url={player.headshot_url ?? null} name={name} size="sm" />
      <div className="min-w-0">
        <p className="truncate text-slate-100">
          <span className={added ? "text-emerald-300" : "text-red-300"}>{added ? "+" : "−"}</span> {name}
        </p>
        <p className="truncate text-slate-500">
          {player.position ?? "?"} {added ? "→" : "←"} {player.team_name ?? "?"}
        </p>
      </div>
    </div>
  );
}

function TradeBody({ tx }: { tx: Transaction }) {
  const sides = tradeSides(tx);
  if (!sides.length) return <p className="mt-2 text-slate-500">{tx.team_names.join(" ↔ ") || "Trade"}</p>;
  return (
    <div className="mt-2">
      <div className={cn("grid gap-3", sides.length > 1 && "sm:grid-cols-2")}>
        {sides.map((side) => (
          <div key={side.team} data-testid="trade-side">
            <p className="mb-1.5 truncate text-[11px] font-medium uppercase tracking-wide text-slate-500">{side.team}</p>
            <div className="space-y-2">
              {side.received.map((player, index) => (
                <TradePlayer key={`got-${player.player_id ?? index}`} player={player} note={fromTeam(tx, player)} />
              ))}
              {side.sent.map((player, index) => (
                <TradePlayer key={`sent-${player.player_id ?? index}`} player={player} note="sent" />
              ))}
            </div>
          </div>
        ))}
      </div>
      {tx.picks?.length ? <p className="mt-2 text-slate-500">Picks: {tx.picks.join(", ")}</p> : null}
    </div>
  );
}

function TradePlayer({ player, note }: { player: TransactionPlayer; note: string | null }) {
  const name = player.player_name ?? "Unknown";
  return (
    <div className="flex items-center gap-2" data-testid="tx-player">
      <PlayerFace url={player.headshot_url ?? null} name={name} size="sm" />
      <div className="min-w-0">
        <p className="truncate text-slate-100">{name}</p>
        <p className="truncate text-slate-500">
          {player.position ?? "?"}
          {note ? ` · ${note}` : ""}
        </p>
      </div>
    </div>
  );
}

type TradeSide = { team: string; received: TransactionPlayer[]; sent: TransactionPlayer[] };

function tradeSides(tx: Transaction): TradeSide[] {
  const receivedIds = new Set(tx.adds.map((player) => player.player_id).filter(Boolean));
  const sides = new Map<string, TradeSide>();
  const side = (name: string | null) => {
    const team = name ?? "Unknown team";
    const row = sides.get(team) ?? { team, received: [], sent: [] };
    sides.set(team, row);
    return row;
  };
  for (const player of tx.adds) side(player.team_name).received.push(player);
  for (const player of tx.drops) {
    if (player.player_id && receivedIds.has(player.player_id)) continue;
    side(player.team_name).sent.push(player);
  }
  const named = tx.team_names.filter((team) => sides.has(team));
  const rest = [...sides.keys()].filter((team) => !named.includes(team));
  return [...named, ...rest].map((team) => sides.get(team)!).filter((row) => row.received.length || row.sent.length);
}

function fromTeam(tx: Transaction, player: TransactionPlayer): string | null {
  const drop = tx.drops.find((row) => row.player_id && row.player_id === player.player_id);
  return drop?.team_name ? `from ${drop.team_name}` : null;
}
