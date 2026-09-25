"""NFL data that prefers the local file, then the ESPN scoreboard.

A projection written into the local file (the demo league) always wins. Vegas
is only used when that file has nothing for the player. Bye weeks and opponents
in the file also win, so the demo seed stays stable.
"""

from app.nfl_data.base import (
    NFLDataProvider,
    PlayerNews,
    PlayerProjection,
    PlayerSeasonStats,
    ScheduleGame,
)
from app.nfl_data.espn import ESPNScheduleClient, GameSummary, SeasonBoard
from app.nfl_data.local_file import LocalFileNFLDataProvider
from app.nfl_data.teams import app_team
from app.nfl_data.vegas import depth_from_extra, project_from_line


class LiveNFLDataProvider(NFLDataProvider):
    name = "espn_vegas"

    def __init__(self, local: LocalFileNFLDataProvider, espn: ESPNScheduleClient):
        self.local = local
        self.espn = espn

    async def _board(self, season: int) -> SeasonBoard:
        return await self.espn.load(season)

    async def get_bye_week(self, nfl_team: str, season: int) -> int | None:
        local = await self.local.get_bye_week(nfl_team, season)
        if local is not None:
            return local
        return (await self._board(season)).bye_week(nfl_team)

    async def get_opponent(self, nfl_team: str, season: int, week: int) -> str | None:
        local = await self.local.get_opponent(nfl_team, season, week)
        if local:
            return local
        game = (await self._board(season)).game(nfl_team, week)
        if game is None:
            return None
        return game.opponent

    async def get_projection(self, player_key: str, season: int, week: int) -> PlayerProjection | None:
        return await self.local.get_projection(player_key, season, week)

    async def get_season_stats(self, player_key: str, season: int) -> PlayerSeasonStats | None:
        return await self.local.get_season_stats(player_key, season)

    async def get_news(self, player_key: str, limit: int = 3) -> list[PlayerNews]:
        return await self.local.get_news(player_key, limit)

    async def get_schedule(self, nfl_team: str, season: int) -> list[ScheduleGame]:
        return (await self._board(season)).season(nfl_team)

    async def live_summaries(self, season: int, week: int) -> list[GameSummary]:
        return await self.espn.live_summaries(season, week)

    async def live_schedule_game(self, nfl_team: str, season: int, week: int) -> ScheduleGame | None:
        slate = await self.espn.live_week(season, week)
        game = slate.get(app_team(nfl_team))
        return game.as_schedule() if game else None

    async def project_from_line(
        self,
        *,
        nfl_team: str,
        position: str | None,
        depth: int | None,
        season: int,
        week: int,
        scoring: dict,
    ) -> PlayerProjection | None:
        game = (await self._board(season)).game(nfl_team, week)
        if game is None or game.opponent is None:
            return None
        return project_from_line(
            week=week,
            position=position,
            depth=depth,
            spread=game.spread,
            total=game.total,
            implied=game.implied_points,
            scoring=scoring,
        )


def depth_for_player(extra: dict | None) -> int | None:
    return depth_from_extra(extra)
