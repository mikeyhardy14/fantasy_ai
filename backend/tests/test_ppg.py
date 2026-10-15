"""PPG blend and projection from Sleeper / ESPN season totals. No network."""

from app.nfl_data.base import PlayerProjection
from app.nfl_data.ppg import (
    SourcePpg,
    blend_ppg,
    espn_scoring_ids,
    espn_source,
    project_from_ppg,
    scoring_column,
    sleeper_source,
)
from app.nfl_data.vegas import explain_projection


def test_scoring_column_follows_reception_points():
    assert scoring_column({"rec": 1})[0] == "pts_ppr"
    assert scoring_column({"rec": 0})[0] == "pts_std"
    assert scoring_column({"rec": 0.5})[0] == "pts_half_ppr"


def test_espn_scoring_ids_average_half_ppr():
    assert espn_scoring_ids({"rec": 1}) == [3]
    assert espn_scoring_ids({"rec": 0}) == [1]
    assert espn_scoring_ids({"rec": 0.5}) == [1, 3]


def test_sleeper_source_divides_season_total_by_games():
    source = sleeper_source({"pts_ppr": 100, "gp": 5}, {"rec": 1})
    assert source is not None
    assert source.points_per_game == 20.0
    assert source.season_points == 100.0
    assert source.games_played == 5


def test_espn_source_uses_applied_average():
    source = espn_source(210.0, 15.0)
    assert source is not None
    assert source.points_per_game == 15.0
    assert source.season_points == 210.0
    assert source.games_played == 14


def test_blend_averages_both_sources():
    blended = blend_ppg(
        SourcePpg(points_per_game=20.0, source="Sleeper PPR"),
        SourcePpg(points_per_game=16.0, source="ESPN"),
    )
    assert blended is not None
    assert blended.points_per_game == 18.0
    projection = project_from_ppg(blended, week=4)
    assert projection.source == "ppg"
    assert projection.points == 18.0
    assert projection.detail["sleeper_ppg"] == 20.0
    assert projection.detail["espn_ppg"] == 16.0
    reasons = explain_projection(projection, on_bye=False, opponent="BUF", team="KC", position="RB")
    assert any("Sleeper" in line and "ESPN" in line for line in reasons)


def test_blend_keeps_a_single_source():
    blended = blend_ppg(SourcePpg(points_per_game=12.4, source="Sleeper PPR"), None)
    assert blended is not None
    assert blended.points_per_game == 12.4
    assert "Sleeper" in blended.note


def test_empty_projection_mentions_ppg_sources():
    reasons = explain_projection(None, on_bye=False, opponent=None, team="KC", position="WR")
    assert any("Sleeper" in line and "ESPN" in line for line in reasons)


def test_explain_accepts_a_saved_projection_unchanged():
    saved = PlayerProjection(week=2, points=12, source="file", detail={})
    reasons = explain_projection(saved, on_bye=False, opponent=None, team="KC", position="RB")
    assert reasons[0].startswith("12 is a saved projection")
