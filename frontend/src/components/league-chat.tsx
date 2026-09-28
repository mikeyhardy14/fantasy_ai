"use client";

import { PlayerFace } from "@/components/player-face";
import { Button } from "@/components/ui/button";
import type { ChatTrade, LeagueMessage } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

export function LeagueChat({
  messages,
  onRespond,
  responding,
}: {
  messages: LeagueMessage[];
  onRespond?: (transactionId: string, action: "accept" | "decline") => void;
  responding?: boolean;
}) {
  if (!messages.length) {
    return <p className="px-5 py-8 text-sm text-slate-400">No messages in this league yet.</p>;
  }
  return (
    <ol className="space-y-4 px-5 py-4" data-testid="league-chat">
      {messages.map((message) => (
        <li key={message.id} data-testid="league-message">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">
            <span className="text-slate-300">{message.author_name}</span>
            <span className="mx-1.5">·</span>
            {relativeTime(message.created_at)}
            {message.pinned ? <span className="ml-2 text-amber-200">Pinned</span> : null}
          </p>
          <p className={cn("mt-1 whitespace-pre-wrap text-sm text-slate-100")}>{message.text}</p>
          {message.trade ? <TradeCard trade={message.trade} onRespond={onRespond} responding={responding} /> : null}
        </li>
      ))}
    </ol>
  );
}

export function TradeCard({
  trade,
  onRespond,
  responding,
}: {
  trade: ChatTrade;
  onRespond?: (transactionId: string, action: "accept" | "decline") => void;
  responding?: boolean;
}) {
  const canAnswer = trade.status === "pending" && trade.involves_user && trade.transaction_id && onRespond;
  return (
    <div className="mt-2" data-testid="chat-trade">
      <div className="grid gap-2 sm:grid-cols-2">
        {trade.sides.map((side) => (
          <div key={side.manager} className="rounded-lg border border-surface-border bg-surface px-3 py-2">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">{side.manager} receives</p>
            <ul className="mt-2 space-y-2 text-sm text-slate-100">
              {side.receives.map((player) => (
                <li key={player.name} className="flex items-center gap-2">
                  <PlayerFace url={player.headshot_url ?? null} name={player.name} size="md" />
                  <span>
                    {player.name}
                    {player.position ? <span className="ml-2 text-xs text-slate-500">{player.position}</span> : null}
                  </span>
                </li>
              ))}
              {side.picks.map((pick) => (
                <li key={pick}>{pick}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {canAnswer ? (
        <div className="mt-3 flex gap-2">
          <Button type="button" data-testid="trade-accept" disabled={responding} onClick={() => onRespond(trade.transaction_id!, "accept")}>
            Accept
          </Button>
          <Button
            type="button"
            variant="secondary"
            data-testid="trade-decline"
            disabled={responding}
            onClick={() => onRespond(trade.transaction_id!, "decline")}
          >
            Decline
          </Button>
        </div>
      ) : null}
    </div>
  );
}
