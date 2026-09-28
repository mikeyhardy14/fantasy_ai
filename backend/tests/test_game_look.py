from app.schemas.league import NflGameOut
from app.services.game_look import game_look


def test_live_look_includes_the_score_clock_and_stat_line():
    game = NflGameOut(away="LV", home="KC", away_score=10, home_score=14, state="in", detail="Q2 4:12")
    look = game_look(
        nfl_team="KC",
        opponent="LV",
        projected_points=16.4,
        points=8.2,
        sleeper_id="100",
        games=[game],
        stats={"100": {"rush_yd": 64, "rush_td": 1}},
        scoring={},
    )
    assert look is not None
    assert look.projected_points == 16.4
    assert look.points == 8.2
    assert look.home is True
    assert look.clock == "Q2 4:12"
    assert look.away_score == 10
    assert look.home_score == 14
    assert look.stat_line == "64 rush yds, 1 rush TD"


def test_a_player_without_a_game_still_keeps_the_projection():
    look = game_look(
        nfl_team="KC",
        opponent=None,
        projected_points=4.0,
        points=None,
        sleeper_id=None,
        games=[],
        stats={},
        scoring={},
    )
    assert look is not None
    assert look.projected_points == 4.0
    assert look.clock is None
    assert look.stat_line is None
