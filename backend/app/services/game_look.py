"""One player's week: projection, fantasy points, NFL score, clock, and counting stats."""

from app.nfl_data.sleeper_stats import score_stats, summarize_stats
from app.schemas.league import GameLookOut, NflGameOut


def index_games(games: list[NflGameOut]) -> dict[str, NflGameOut]:
    index: dict[str, NflGameOut] = {}
    for game in games:
        if game.away:
            index.setdefault(game.away, game)
        if game.home:
            index.setdefault(game.home, game)
    return index


def game_look(
    *,
    nfl_team: str | None,
    opponent: str | None,
    projected_points: float | None,
    points: float | None,
    sleeper_id: str | None,
    games: list[NflGameOut],
    stats: dict,
    scoring: dict | None,
    games_by_team: dict[str, NflGameOut] | None = None,
) -> GameLookOut | None:
    game = _game_for(games, nfl_team, games_by_team)
    raw = stats.get(sleeper_id) if sleeper_id else None
    line = summarize_stats(raw) if isinstance(raw, dict) else ""
    scored = points
    if scored is None and isinstance(raw, dict):
        scored, _label = score_stats(raw, scoring)
    if game is None and not line and scored is None and projected_points is None:
        return None
    home = None
    if game is not None and nfl_team:
        home = game.home == nfl_team
    return GameLookOut(
        projected_points=projected_points,
        points=scored,
        stat_line=line or None,
        opponent=opponent,
        home=home,
        away=game.away if game else None,
        home_team=game.home if game else None,
        away_score=game.away_score if game else None,
        home_score=game.home_score if game else None,
        state=game.state if game else None,
        clock=game.detail if game else None,
        possession=game.possession if game else None,
    )


def _game_for(
    games: list[NflGameOut],
    nfl_team: str | None,
    games_by_team: dict[str, NflGameOut] | None = None,
) -> NflGameOut | None:
    if not nfl_team:
        return None
    code = nfl_team.upper()
    if games_by_team is not None:
        return games_by_team.get(code)
    for game in games:
        if game.away == code or game.home == code:
            return game
    return None
