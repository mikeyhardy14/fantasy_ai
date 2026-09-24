"""External NFL data (projections, bye weeks, news, stats).

Deliberately separate from FantasyProvider: league/roster data comes from the
fantasy platform; player analysis data comes from here. Anything a provider
does not know is returned as None so downstream code reports "unavailable"
instead of fabricating numbers.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class PlayerProjection(BaseModel):
    week: int
    points: float
    source: str
    detail: dict[str, float] = Field(default_factory=dict)
    note: str | None = None


class ScheduleGame(BaseModel):
    """One regular-season week. opponent is null on a bye."""

    week: int
    opponent: str | None = None
    home: bool | None = None
    spread: float | None = None
    total: float | None = None
    implied_points: float | None = None
    win_probability: float | None = None
    book_count: int = 0
    books: list[str] = Field(default_factory=list)


class PlayerNews(BaseModel):
    headline: str
    published_at: str | None = None
    source: str | None = None
    body: str | None = None


class PlayerSeasonStats(BaseModel):
    season: int
    games_played: int | None = None
    fantasy_points: float | None = None
    fantasy_points_per_game: float | None = None
    detail: dict[str, float] = Field(default_factory=dict)
    source: str | None = None


class NFLDataProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    async def get_bye_week(self, nfl_team: str, season: int) -> int | None:
        ...

    @abstractmethod
    async def get_projection(
        self, player_key: str, season: int, week: int
    ) -> PlayerProjection | None:
        """player_key is 'name|position|team' - the neutral key defined in
        app.nfl_data.keys so this layer never depends on provider ids."""

    @abstractmethod
    async def get_season_stats(self, player_key: str, season: int) -> PlayerSeasonStats | None:
        ...

    @abstractmethod
    async def get_news(self, player_key: str, limit: int = 3) -> list[PlayerNews]:
        ...

    @abstractmethod
    async def get_opponent(self, nfl_team: str, season: int, week: int) -> str | None:
        ...

    async def get_schedule(self, nfl_team: str, season: int) -> list[ScheduleGame]:
        """Remaining and past regular-season games. Empty when the source has no slate."""
        return []

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
        """Vegas-derived points. None unless a provider has a posted line."""
        return None


def player_key(name: str, position: str | None, nfl_team: str | None) -> str:
    return f"{name.strip().lower()}|{(position or '').upper()}|{(nfl_team or '').upper()}"
