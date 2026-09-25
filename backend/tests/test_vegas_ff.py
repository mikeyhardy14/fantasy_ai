"""The Vegas share model: history, team volume, and start/sit. No network."""

from app.nfl_data.base import PlayerProjection
from app.nfl_data.usage import build_usage
from app.nfl_data.vegas import explain_projection
from app.nfl_data.vegas_ff import (
    ewma,
    implied_totals,
    project_player,
    scoring_from_league,
    share_projection,
    start_sit,
    team_projection,
)


def test_ewma_skips_missing_and_weights_the_newest_game():
    # reversed: 3 at weight 1, then 1 at weight 0.5. None is skipped.
    assert ewma([1, None, 3], 0.5) == 3.5 / 1.5


def test_implied_totals_split_the_number_and_the_margin():
    sides = implied_totals(47, -3)
    assert sides["home"] == (25, 3)
    assert sides["away"] == (22, -3)


def test_team_volume_follows_the_fitted_line():
    history = {stat: [30, 30, 30] for stat in ("pass_att", "completions", "pass_yds", "pass_td", "ints", "rush_att", "rush_yds", "rush_td")}
    volume = team_projection(24, 3, history)
    # 6.0938 + 0.4928*24 - 0.2499*3 + 0.4854*30
    assert round(volume["pass_att"], 4) == 31.7333
    assert volume["pass_att"] > 0


def test_share_is_the_players_fraction_of_the_team_stat():
    game = {stat: 0 for stat in ("pass_att", "pass_yds", "pass_td", "ints", "rush_att", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td")}
    game["pass_att"] = 20
    for stat in ("pass_att", "completions", "pass_yds", "pass_td", "ints", "rush_att", "rush_yds", "rush_td"):
        game["team_" + stat] = 40
    team = {stat: 0.0 for stat in ("pass_att", "completions", "pass_yds", "pass_td", "ints", "rush_att", "rush_yds", "rush_td")}
    team["pass_att"] = 32
    proj = share_projection([game], team)
    assert proj["pass_att"] == 16


def test_start_sit_picks_the_player_who_always_scores_more():
    result = start_sit([20, 20, 20], [10, 10, 10], "Wide One", "Wide Two")
    assert result["start"] == "Wide One"
    assert result["win_prob"] == 1.0
    assert result["confidence"] == "strong start"
    assert result["median"] == (20.0, 10.0)


def test_a_close_split_is_a_coin_flip():
    result = start_sit([10, 9], [9, 10], "A", "B")
    assert result["win_prob"] == 0.5
    assert result["confidence"] == "coin flip"


def test_half_ppr_changes_the_reception_rate():
    scoring = scoring_from_league({"rec": 0.5, "pass_int": -1})
    assert scoring["rec"] == 0.5
    assert scoring["int"] == -1
    assert scoring["pass_yd"] == 0.04


def test_usage_sums_the_team_and_keeps_the_projected_week_out():
    weeks = [
        (1, {"qb": {"pass_yd": 200, "pass_att": 30}, "wr": {"rec": 5, "rec_yd": 60, "rec_tgt": 8, "rec_air_yd": 70}}),
        (2, {"qb": {"pass_yd": 100, "pass_att": 20}, "wr": {"rec": 4, "rec_yd": 40, "rec_tgt": 6}}),
    ]
    teams = {"qb": "KC", "wr": "KC"}
    table = build_usage(weeks, teams, {"wr": "Out", "qb": None}, {"qb": "QB", "wr": "WR"})
    assert table.team_history["KC"]["pass_yds"] == [200, 100]
    assert table.team_history["KC"]["targets"] == [8, 6]
    assert [game["_week"] for game in table.games["wr"]] == [1, 2]
    assert table.games["wr"][0]["targets"] == 8
    assert table.games["wr"][0]["routes"] is None
    assert table.games["wr"][0]["ez_targets"] is None
    assert table.team_history["KC"]["ez_targets"] == [None, None]


def test_receiver_projection_uses_the_earlier_game_only():
    weeks = [(1, {"wr": {"rec": 6, "rec_yd": 80, "rec_tgt": 10, "rec_td": 1, "off_snp": 50, "tm_off_snp": 60}})]
    table = build_usage(weeks, {"wr": "KC"}, {}, {"wr": "WR"})
    projection = project_player(
        position="WR",
        week=2,
        implied=24,
        margin=3,
        team_history=table.team_history["KC"],
        player_games=table.games["wr"],
    )
    assert projection is not None
    assert projection.source == "vegas"
    assert projection.points > 0
    assert projection.detail["vegas_ff"] == 1
    assert projection.detail["games"] == 1
    reasons = explain_projection(projection, on_bye=False, opponent="BUF", team="KC", position="WR")
    assert any("earlier" in line for line in reasons)
    assert any("snap share" in line for line in reasons)


def test_no_history_is_not_a_zero_projection():
    assert project_player(position="RB", week=2, implied=24, margin=1, team_history={}, player_games=[]) is None


def test_empty_projection_mentions_both_missing_inputs():
    reasons = explain_projection(None, on_bye=False, opponent=None, team="KC", position="WR")
    assert any("earlier game" in line and "prop line" in line for line in reasons)


def test_explain_accepts_a_saved_projection_unchanged():
    saved = PlayerProjection(week=2, points=12, source="file", detail={})
    reasons = explain_projection(saved, on_bye=False, opponent=None, team="KC", position="RB")
    assert reasons[0].startswith("12 is a saved projection")
