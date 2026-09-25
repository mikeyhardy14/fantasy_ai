"use client";

import { MatchupCompare } from "@/components/matchup-compare";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import type { LeagueMatchup } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";

export function MatchupSlate({ games, week }: { games: LeagueMatchup[]; week: number }) {
  const others = games.filter((game) => !game.involves_user);
  const [openId, setOpenId] = useState<string | null>(null);
  if (!others.length) return null;
  return (
    <Card>
      <CardHeader title="Other matchups" description={`The rest of week ${week}. Open a game to compare starters.`} />
      <ul className="divide-y divide-surface-border/60">
        {others.map((game) => {
          const id = `${game.team.team.id}:${game.opponent?.team.id ?? "bye"}`;
          const open = openId === id;
          return (
            <li key={id} data-testid="other-matchup" className="px-5 py-3">
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                <Score name={game.team.team.name} teamId={game.team.team.id} record={game.team.team.record} points={game.team.points} projected={game.team.projected_points} />
                <div className="text-center">
                  <Badge className="bg-slate-500/15 text-slate-300 ring-slate-500/30">{game.status.replace("_", " ")}</Badge>
                  {game.opponent ? (
                    <button
                      type="button"
                      className="mt-2 block text-[11px] text-slate-400 hover:text-slate-100"
                      aria-expanded={open}
                      onClick={() => setOpenId(open ? null : id)}
                    >
                      {open ? "Hide starters" : "Starters"}
                    </button>
                  ) : null}
                </div>
                {game.opponent ? (
                  <Score name={game.opponent.team.name} teamId={game.opponent.team.id} record={game.opponent.team.record} points={game.opponent.points} projected={game.opponent.projected_points} right />
                ) : (
                  <p className="text-right text-sm text-slate-400">Bye</p>
                )}
              </div>
              {open && game.opponent ? (
                <MatchupCompare
                  week={week}
                  yours={game.team.starters}
                  theirs={game.opponent.starters}
                  yourName={game.team.team.name}
                  theirName={game.opponent.team.name}
                />
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function Score({
  name,
  teamId,
  record,
  points,
  projected,
  right,
}: {
  name: string;
  teamId: string;
  record: string;
  points: number;
  projected: number | null;
  right?: boolean;
}) {
  return (
    <div className={cn("min-w-0", right && "text-right")}>
      <Link href={`/teams/${teamId}`} className="truncate text-sm font-semibold text-slate-100 hover:underline">
        {name}
      </Link>
      <p className="text-[11px] text-slate-500">{record}</p>
      <p className="text-lg font-semibold tabular-nums text-slate-100">{formatPoints(points)}</p>
      <p className="text-[11px] text-slate-500">Proj {formatPoints(projected)}</p>
    </div>
  );
}
