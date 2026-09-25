"""Counting stats attach only while that player's game is in progress."""

from uuid import uuid4

from app.schemas.league import (
    MatchupOut,
    MatchupSideOut,
    NflGameOut,
    PlayerOut,
    RosterSlotOut,
    TeamSummaryOut,
)
from app.services.league_context import _apply_live_stat_lines


def _player(name: str, team: str, sleeper_id: str) -> PlayerOut:
    return PlayerOut(id=uuid4(), name=name, position="RB", nfl_team=team, external_ids={"sleeper": sleeper_id})


def _side(player: PlayerOut) -> MatchupSideOut:
    team = TeamSummaryOut(
        id=uuid4(), name="Side", wins=1, losses=0, ties=0, record="1-0", points_for=10, points_against=8
    )
    return MatchupSideOut(
        team=team,
        points=10,
        projected_points=12,
        starters=[RosterSlotOut(slot="RB", slot_index=1, is_starter=True, player=player)],
    )


def test_stat_line_is_added_only_for_the_team_that_is_playing():
    live = _side(_player("Live Back", "KC", "100"))
    waiting = _side(_player("Waiting", "DAL", "200"))
    view = MatchupOut(
        week=4,
        is_bye=False,
        user=live,
        opponent=waiting,
        status="in_progress",
        games=[NflGameOut(away="BUF", home="KC", state="in", detail="8:22 - 2nd")],
    )
    _apply_live_stat_lines(view, {"100": {"rush_yd": 64, "rush_td": 1}, "200": {"rush_yd": 12}})
    assert live.starters[0].stat_line == "64 rush yds, 1 rush TD"
    assert waiting.starters[0].stat_line is None


def test_a_finished_game_does_not_get_a_stat_line():
    done = _side(_player("Done Back", "KC", "100"))
    view = MatchupOut(
        week=4,
        is_bye=False,
        user=done,
        opponent=None,
        status="in_progress",
        games=[NflGameOut(away="BUF", home="KC", state="post", detail="Final")],
    )
    _apply_live_stat_lines(view, {"100": {"rush_yd": 80}})
    assert done.starters[0].stat_line is None
