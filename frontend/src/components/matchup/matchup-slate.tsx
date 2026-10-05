"use client";

import { HotList, hotPlayers } from "@/components/matchup/hot-list";
import { MatchupCompare } from "@/components/matchup/matchup-compare";
import { ScoreBox, ScoreBoxSide, ScoreMark } from "@/components/matchup/score-box";
import { Card, CardHeader } from "@/components/ui/card";
import { Pop } from "@/components/ui/pop";
import type { LeagueMatchup, MatchupSide, NflGame } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";

function slateOver(nfl: NflGame[] | undefined): boolean {
  if (!nfl?.length) return false;
  return nfl.every((game) => game.state === "post");
}

function fantasyStatus(game: LeagueMatchup, nfl?: NflGame[]): string {
  if (game.status === "bye") return "Bye";
  if (game.status === "final" || slateOver(nfl)) return "Final";
  if (game.status === "in_progress") return "Live";
  return "Upcoming";
}

function fantasyLive(game: LeagueMatchup, nfl?: NflGame[]): boolean {
  return game.status === "in_progress" && !slateOver(nfl);
}

function sideAhead(game: LeagueMatchup, which: "team" | "opponent"): boolean {
  if (!game.opponent) return false;
  if (game.team.points === game.opponent.points) return false;
  return which === "team" ? game.team.points > game.opponent.points : game.opponent.points > game.team.points;
}

function sideDetail(side: MatchupSide): string {
  return `${side.team.record} · Proj ${formatPoints(side.projected_points)}`;
}

export function MatchupSlate({ games, week, nfl }: { games: LeagueMatchup[]; week: number; nfl?: NflGame[] }) {
  const others = games.filter((game) => !game.involves_user);
  const [openId, setOpenId] = useState<string | null>(null);
  if (!others.length) return null;
  return (
    <Card>
      <CardHeader title="Other matchups" description={`The rest of week ${week}. Open a game to compare starters.`} />
      <ul className="grid gap-1.5 p-4 sm:grid-cols-2 xl:grid-cols-3">
        {others.map((game) => {
          const id = `${game.team.team.id}:${game.opponent?.team.id ?? "bye"}`;
          const open = openId === id;
          const live = fantasyLive(game, nfl);
          return (
            <li key={id} data-testid="other-matchup">
              <ScoreBox
                as="div"
                live={live}
                status={fantasyStatus(game, nfl)}
                footer={
                  game.opponent ? (
                    <button
                      type="button"
                      className="text-[11px] text-slate-400 hover:text-slate-100"
                      aria-expanded={open}
                      onClick={() => setOpenId(open ? null : id)}
                    >
                      {open ? "Hide starters" : "Starters"}
                    </button>
                  ) : null
                }
              >
                <FantasySide side={game.team} ahead={sideAhead(game, "team")} />
                {game.opponent ? (
                  <FantasySide side={game.opponent} ahead={sideAhead(game, "opponent")} />
                ) : (
                  <ScoreBoxSide name="Bye" score="—" />
                )}
              </ScoreBox>
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
      <ul className="grid grid-cols-1 gap-1.5 p-2 sm:grid-cols-2 xl:grid-cols-3" data-testid="league-games">
        {games.map((game) => {
          const id = `${game.team.team.id}:${game.opponent?.team.id ?? "bye"}`;
          const live = fantasyLive(game, nfl);
          return (
            <li key={id} data-testid="league-game" data-yours={game.involves_user ? "true" : "false"}>
              <ScoreBox
                live={live}
                highlight={game.involves_user}
                compact
                status={fantasyStatus(game, nfl)}
                disabled={!game.opponent}
                onClick={() => game.opponent && setOpen(game)}
              >
                <ScoreBoxSide
                  mark={<ScoreMark src={game.team.team.avatar} label={game.team.team.name} />}
                  name={game.team.team.name}
                  score={formatPoints(game.team.points)}
                  ahead={sideAhead(game, "team")}
                />
                {game.opponent ? (
                  <ScoreBoxSide
                    mark={<ScoreMark src={game.opponent.team.avatar} label={game.opponent.team.name} />}
                    name={game.opponent.team.name}
                    score={formatPoints(game.opponent.points)}
                    ahead={sideAhead(game, "opponent")}
                  />
                ) : (
                  <ScoreBoxSide name="Bye" score="—" />
                )}
              </ScoreBox>
            </li>
          );
        })}
      </ul>
      {open?.opponent ? (
        <Pop title={`${open.team.team.name} vs ${open.opponent.team.name}`} onClose={() => setOpen(null)} wide>
          <div className="space-y-2 border-b border-white/10 px-4 py-3" data-testid="game-score">
            <ScoreBoxSide
              mark={<ScoreMark src={open.team.team.avatar} label={open.team.team.name} size="md" />}
              name={
                <Link
                  href={open.team.team.is_user_team || open.involves_user ? "/team" : `/teams/${open.team.team.id}`}
                  className={cn("truncate hover:underline", open.team.team.is_user_team || open.involves_user ? "text-emerald-100" : "text-slate-100")}
                >
                  {open.team.team.name}
                </Link>
              }
              score={formatPoints(open.team.points)}
              detail={sideDetail(open.team)}
              ahead={sideAhead(open, "team")}
            />
            <ScoreBoxSide
              mark={<ScoreMark src={open.opponent.team.avatar} label={open.opponent.team.name} size="md" />}
              name={
                <Link
                  href={open.opponent.team.is_user_team ? "/team" : `/teams/${open.opponent.team.id}`}
                  className={cn("truncate hover:underline", open.opponent.team.is_user_team ? "text-emerald-100" : "text-slate-100")}
                >
                  {open.opponent.team.name}
                </Link>
              }
              score={formatPoints(open.opponent.points)}
              detail={sideDetail(open.opponent)}
              ahead={sideAhead(open, "opponent")}
            />
            <p className="text-xs text-slate-400">{open.status.replace("_", " ")}</p>
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

function FantasySide({ side, ahead }: { side: MatchupSide; ahead: boolean }) {
  return (
    <ScoreBoxSide
      mark={<ScoreMark src={side.team.avatar} label={side.team.name} />}
      name={
        <Link href={side.team.is_user_team ? "/team" : `/teams/${side.team.id}`} className="truncate hover:underline">
          {side.team.name}
        </Link>
      }
      score={formatPoints(side.points)}
      detail={sideDetail(side)}
      ahead={ahead}
    />
  );
}
