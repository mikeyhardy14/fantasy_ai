"""Available-player browse keeps the highest projections, not the first names."""

from types import SimpleNamespace
from uuid import uuid4

from app.nfl_data.base import PlayerProjection
from app.schemas.league import PlayerOut
from app.services.league_context import LeagueContextService


class _Board:
    async def get_bye_week(self, team, season):
        return None


def _service() -> LeagueContextService:
    return LeagueContextService(session=SimpleNamespace(), nfl_data=_Board())  # type: ignore[arg-type]


def _league():
    return SimpleNamespace(id=uuid4(), provider="sleeper", season=2026, current_week=4)


def _player(name: str):
    return SimpleNamespace(name=name, nfl_team="KC", position="RB")


async def test_a_position_browse_returns_the_higher_projection():
    service = _service()
    seen: dict = {}
    early = _player("Aaron Early")
    late = _player("Zack Late")

    async def search(**kwargs):
        seen.update(kwargs)
        return [early, late]

    async def rostered(*_args, **_kwargs):
        return set()

    async def project(player, league, week, on_bye):
        points = 2.0 if player.name == "Aaron Early" else 18.4
        return PlayerProjection(week=week, points=points, source="test")

    async def player_out(player, league, week):
        points = 2.0 if player.name == "Aaron Early" else 18.4
        return PlayerOut(id=uuid4(), name=player.name, position="RB", nfl_team="KC", projected_points=points)

    service.players.search = search  # type: ignore[method-assign]
    service.players.rostered_player_ids = rostered  # type: ignore[method-assign]
    service._week_projection = project  # type: ignore[method-assign]
    service.player_out = player_out  # type: ignore[method-assign]

    rows = await service.available_players(_league(), position="RB", limit=1)
    assert seen["limit"] == 2000
    assert [row.name for row in rows] == ["Zack Late"]


async def test_a_name_search_stays_a_small_list():
    service = _service()
    seen: dict = {}

    async def search(**kwargs):
        seen.update(kwargs)
        return []

    async def rostered(*_args, **_kwargs):
        return set()

    service.players.search = search  # type: ignore[method-assign]
    service.players.rostered_player_ids = rostered  # type: ignore[method-assign]

    await service.available_players(_league(), position="RB", search="zack", limit=1)
    assert seen["limit"] == 1
    assert seen["query"] == "zack"
