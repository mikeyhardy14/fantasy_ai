import type { GameLook } from "@/lib/types";
import { formatPoints } from "@/lib/utils";

export function gameScore(game: GameLook): string | null {
  if (game.state === "pre" || game.away_score == null || game.home_score == null || !game.away || !game.home_team) return null;
  return `${game.away} ${game.away_score}, ${game.home_team} ${game.home_score}`;
}

export function PlayerGameLine({ game }: { game?: GameLook | null }) {
  if (!game) return null;
  const bits = [gameScore(game), game.clock, game.points != null ? `${formatPoints(game.points)} pts` : null, game.stat_line].filter(
    (bit): bit is string => Boolean(bit),
  );
  if (!bits.length) return null;
  return (
    <p className="text-[11px] leading-snug text-slate-400" data-testid="player-game">
      {bits.join(" · ")}
    </p>
  );
}
