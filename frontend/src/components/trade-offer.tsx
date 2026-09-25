"use client";

import { Badge, PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { InlineError } from "@/components/ui/states";
import { api } from "@/lib/api";
import { readLineupAutoApprove } from "@/lib/lineup-approval";
import type { Player, Team, TradeAnalysis } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useState } from "react";

const VERDICT_STYLE: Record<TradeAnalysis["verdict"], string> = {
  ACCEPT: "bg-emerald-500/15 text-emerald-200 ring-emerald-500/30",
  REJECT: "bg-red-500/15 text-red-200 ring-red-500/30",
  NEGOTIATE: "bg-amber-500/15 text-amber-200 ring-amber-500/30",
  UNCLEAR: "bg-slate-500/15 text-slate-200 ring-slate-500/30",
};

function rosterPlayers(team: Team): Player[] {
  return [...team.starters, ...team.bench, ...team.reserve].map((slot) => slot.player).filter((player): player is Player => !!player);
}

export function TradeOffer({ leagueId, mine, opponent }: { leagueId: string; mine: Team; opponent: Team }) {
  const yours = rosterPlayers(mine);
  const theirs = rosterPlayers(opponent);
  const [give, setGive] = useState<Player[]>([]);
  const [receive, setReceive] = useState<Player[]>([]);

  const ask = useMutation({
    mutationFn: () => api.ai.chat(leagueId, [{ role: "user", content: offerPrompt(opponent, give, receive) }], readLineupAutoApprove()),
  });
  const analyze = useMutation({
    mutationFn: () => api.ai.trade(leagueId, { give: give.map((player) => player.id), receive: receive.map((player) => player.id) }),
  });

  const toggle = (list: Player[], set: (next: Player[]) => void, player: Player) =>
    set(list.some((item) => item.id === player.id) ? list.filter((item) => item.id !== player.id) : list.length < 6 ? [...list, player] : list);

  return (
    <Card>
      <CardHeader
        title={`Offer ${opponent.team.name} a trade`}
        description="Pick players on both sides, or ask the assistant to propose one. The offer stays here. It is not sent to the league."
      />
      <CardBody className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Picker title="You give" players={yours} selected={give} onToggle={(player) => toggle(give, setGive, player)} />
          <Picker title="You receive" players={theirs} selected={receive} onToggle={(player) => toggle(receive, setReceive, player)} />
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-300">{give.map((player) => player.name).join(", ") || "No players to give"}</span>
          <ArrowLeftRight className="h-4 w-4 text-slate-500" />
          <span className="text-slate-300">{receive.map((player) => player.name).join(", ") || "No players to receive"}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => ask.mutate()} loading={ask.isPending} data-testid="ask-trade">
            Ask the assistant
          </Button>
          <Button
            variant="secondary"
            onClick={() => analyze.mutate()}
            disabled={!give.length || !receive.length}
            loading={analyze.isPending}
            data-testid="analyze-offer"
          >
            Analyze this offer
          </Button>
        </div>
        <InlineError error={ask.error ?? analyze.error} />
        {ask.data ? (
          <div className="prose-chat border border-surface-border bg-surface-overlay px-4 py-3 text-sm text-slate-200" data-testid="trade-advice">
            <ReactMarkdown>{ask.data.message}</ReactMarkdown>
          </div>
        ) : null}
        {analyze.data ? (
          <div data-testid="trade-result">
            <Badge className={VERDICT_STYLE[analyze.data.analysis.verdict]}>{analyze.data.analysis.verdict}</Badge>
            <p className="mt-2 text-sm text-slate-200">{analyze.data.analysis.summary}</p>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

function offerPrompt(opponent: Team, give: Player[], receive: Player[]): string {
  const team = `${opponent.team.name} (team_id ${opponent.team.id})`;
  if (!give.length && !receive.length) {
    return `Propose one trade I should offer ${team}. Call get_team_roster for that team_id, plus get_roster and get_roster_needs. Name the players I give and the players I receive. Do not claim the trade was sent.`;
  }
  const sent = give.map((player) => player.name).join(", ") || "nobody yet";
  const got = receive.map((player) => player.name).join(", ") || "nobody yet";
  return `I want to offer ${team} a trade. I would give ${sent}. I would receive ${got}. Call get_team_roster for that team_id and get_roster. Say whether I should send this offer and what to change. Do not claim it was sent.`;
}

function Picker({
  title,
  players,
  selected,
  onToggle,
}: {
  title: string;
  players: Player[];
  selected: Player[];
  onToggle: (player: Player) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-[11px] uppercase tracking-wide text-slate-500">{title}</p>
      <div className="max-h-72 space-y-1 overflow-y-auto">
        {players.map((player) => {
          const active = selected.some((item) => item.id === player.id);
          return (
            <button
              key={player.id}
              type="button"
              onClick={() => onToggle(player)}
              className={cn(
                "flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left text-sm hover:bg-surface-overlay",
                active && "bg-brand-soft/40 ring-1 ring-inset ring-emerald-500/40",
              )}
            >
              <span className="flex min-w-0 items-center gap-2">
                <PositionBadge position={player.position} />
                <span className="truncate text-slate-100">{player.name}</span>
              </span>
              <span className="shrink-0 text-[10px] tabular-nums text-slate-500">proj {formatPoints(player.projected_points)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
