import { PlayerFace } from "@/components/player/player-face";
import type { Transaction, TransactionPlayer } from "@/lib/types";

export function OutstandingTrades({
  trades,
  userTeamId,
  userTeamName,
}: {
  trades: Transaction[];
  userTeamId?: string;
  userTeamName?: string | null;
}) {
  const open = trades.filter((trade) => trade.status === "pending" && trade.involves_user);
  if (!open.length) {
    return <p className="px-5 py-6 text-sm text-slate-400">No outstanding offers. A sent trade stays here until the other manager answers it in Sleeper.</p>;
  }
  return (
    <ul className="divide-y divide-surface-border">
      {open.map((trade) => {
        const { send, receive } = offerSides(trade, userTeamId);
        const other = trade.team_names.find((name) => name && name !== userTeamName) ?? "the other manager";
        const title = send.length ? `Offer to ${other}` : `Offer from ${other}`;
        return (
          <li key={trade.id} className="space-y-3 px-5 py-4" data-testid="outstanding-trade">
            <p className="text-sm text-slate-100">
              {title}
              <span className="ml-2 text-[11px] uppercase tracking-wide text-amber-200">Pending</span>
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <OfferSide label="You send" players={send} />
              <OfferSide label="You receive" players={receive} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function OfferSide({ label, players }: { label: string; players: TransactionPlayer[] }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      {players.length ? (
        <ul className="mt-2 space-y-2">
          {players.map((player, index) => (
            <li key={player.player_id ?? index} className="flex items-center gap-3">
              <PlayerFace url={player.headshot_url ?? null} name={player.player_name ?? "Player"} size="md" />
              <span className="text-sm text-slate-100">
                {player.player_name ?? "Unknown"}
                {player.position ? <span className="ml-2 text-xs text-slate-500">{player.position}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Nothing</p>
      )}
    </div>
  );
}

function offerSides(trade: Transaction, userTeamId?: string) {
  if (!userTeamId) return { send: trade.drops, receive: trade.adds };
  return {
    send: trade.drops.filter((player) => player.team_id === userTeamId),
    receive: trade.adds.filter((player) => player.team_id === userTeamId),
  };
}
