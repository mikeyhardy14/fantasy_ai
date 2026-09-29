"use client";

import { HotList, hotPlayers } from "@/components/matchup/hot-list";
import { MatchupCompare } from "@/components/matchup/matchup-compare";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { Pop } from "@/components/ui/pop";
import type { LeagueMatchup, NflGame } from "@/lib/types";
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

export function LeagueGames({
  games,
  week,
  nfl = [],
  current = true,
}: {
  games: LeagueMatchup[];
  week: number;
  nfl?: NflGame[];
  current?: boolean;
}) {
  const [open, setOpen] = useState<LeagueMatchup | null>(null);
  if (!games.length) return <p className="px-3 py-4 text-xs text-slate-400">No games this week.</p>;
  return (
    <>
      <ul data-testid="league-games">
        {games.map((game) => {
          const id = `${game.team.team.id}:${game.opponent?.team.id ?? "bye"}`;
          const live = game.status === "in_progress";
          return (
            <li
              key={id}
              data-testid="league-game"
              data-yours={game.involves_user ? "true" : "false"}
              className={cn(game.involves_user && "bg-emerald-400/10")}
            >
              <button
                type="button"
                className="grid w-full grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 px-3 py-1.5 text-left hover:bg-white/5 disabled:cursor-default"
                disabled={!game.opponent}
                onClick={() => game.opponent && setOpen(game)}
              >
                <ScoreLine name={game.team.team.name} points={game.team.points} yours={game.team.team.is_user_team || game.involves_user} />
                <span className={cn("shrink-0 text-[10px] uppercase tracking-wide", live ? "font-semibold text-red-300" : "text-slate-500")}>
                  {live ? "Live" : game.status === "final" ? "Final" : "vs"}
                </span>
                {game.opponent ? (
                  <ScoreLine name={game.opponent.team.name} points={game.opponent.points} yours={game.opponent.team.is_user_team} right />
                ) : (
                  <span className="text-right text-xs text-slate-400">Bye</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {open?.opponent ? (
        <Pop title={`${open.team.team.name} vs ${open.opponent.team.name}`} onClose={() => setOpen(null)} wide>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-white/10 px-4 py-3" data-testid="game-score">
            <GameScore
              name={open.team.team.name}
              teamId={open.team.team.id}
              record={open.team.team.record}
              points={open.team.points}
              projected={open.team.projected_points}
              yours={open.team.team.is_user_team || open.involves_user}
            />
            <span className="text-[11px] uppercase tracking-wide text-slate-400">{open.status.replace("_", " ")}</span>
            <GameScore
              name={open.opponent.team.name}
              teamId={open.opponent.team.id}
              record={open.opponent.team.record}
              points={open.opponent.points}
              projected={open.opponent.projected_points}
              yours={open.opponent.team.is_user_team}
              right
            />
          </div>
          <div className="border-b border-white/10">
            <p className="px-4 pt-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">
              {[...open.team.starters, ...open.opponent.starters].some((slot) => (slot.points ?? 0) > 0 || slot.stat_line || slot.game?.stat_line)
                ? "Playing well"
                : "Top projections"}
            </p>
            <HotList slots={hotPlayers([...open.team.starters, ...open.opponent.starters])} />
          </div>
          <MatchupCompare
            week={week}
            yours={open.team.starters}
            theirs={open.opponent.starters}
            yourName={open.team.team.name}
            theirName={open.opponent.team.name}
            games={nfl}
            current={current}
          />
        </Pop>
      ) : null}
    </>
  );
}

function GameScore({
  name,
  teamId,
  record,
  points,
  projected,
  yours,
  right,
}: {
  name: string;
  teamId: string;
  record: string;
  points: number;
  projected: number | null;
  yours?: boolean;
  right?: boolean;
}) {
  return (
    <div className={cn("min-w-0", right && "text-right")}>
      <Link href={yours ? "/team" : `/teams/${teamId}`} className={cn("truncate text-sm font-medium hover:underline", yours ? "text-emerald-100" : "text-slate-100")}>
        {name}
      </Link>
      <p className="font-serif text-3xl tabular-nums text-slate-100">{formatPoints(points)}</p>
      <p className="text-[11px] text-slate-500">{record} · {formatPoints(projected)}</p>
    </div>
  );
}

function ScoreLine({ name, points, yours, right }: { name: string; points: number; yours?: boolean; right?: boolean }) {
  return (
    <span className={cn("flex min-w-0 items-baseline gap-2", right && "flex-row-reverse")}>
      <span className={cn("truncate text-xs", yours ? "font-medium text-emerald-100" : "text-slate-200")}>{name}</span>
      <span className="shrink-0 tabular-nums text-sm text-slate-100">{formatPoints(points)}</span>
    </span>
  );
}

function Score({
  name,
  teamId,
  record,
  points,
  projected,
  right,
  yours,
}: {
  name: string;
  teamId: string;
  record: string;
  points: number;
  projected: number | null;
  right?: boolean;
  yours?: boolean;
}) {
  return (
    <div className={cn("min-w-0", right && "text-right")}>
      <Link href={yours ? "/team" : `/teams/${teamId}`} className="truncate text-sm font-semibold text-slate-100 hover:underline">
        {name}
      </Link>
      <p className="text-[11px] text-slate-500">{record}</p>
      <p className="text-lg font-semibold tabular-nums text-slate-100">{formatPoints(points)}</p>
      <p className="text-[11px] text-slate-500">Proj {formatPoints(projected)}</p>
    </div>
  );
}
