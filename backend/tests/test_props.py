"""Player prop lines become fantasy points. No network."""

from app.nfl_data.market import american_probability
from app.nfl_data.props import parse_prop_items, project_player_props, prop_components
from app.nfl_data.sleeper_stats import recent_game
from app.nfl_data.vegas import explain_projection


def test_rush_line_is_ten_points():
    projection = project_player_props({"rush_yd": 100.5}, {"rush_yd": 0.1, "rush_td": 6}, week=3)
    assert projection is not None
    assert prop_components(projection.detail)[0]["label"] == "Rush yds"
    assert prop_components(projection.detail)[0]["points"] == 10.05
    assert projection.points == 10.1
    assert projection.source == "vegas"
    reasons = explain_projection(projection, on_bye=False, opponent="LV", team="KC", position="RB")
    assert any("DraftKings" in line for line in reasons)


def test_parser_keeps_full_game_lines_and_drops_milestones():
    items = [
        {
            "athlete": {"$ref": "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/3149687"},
            "type": {"name": "Total Rushing Yards (incl. overtime)"},
            "current": {"target": {"value": 100.5}},
        },
        {
            "athlete": {"$ref": "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/3149687"},
            "type": {"name": "Rushing Yards Milestones"},
            "current": {"target": {"value": 100}},
        },
        {
            "athlete": {"$ref": "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/3149687"},
            "type": {"name": "Anytime Touchdown Scorer"},
            "current": {},
        },
        {
            "athlete": {"$ref": "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/3149687"},
            "type": {"name": "Total Receptions (incl. overtime)"},
            "current": {"target": {"value": 4.5}},
        },
    ]
    parsed = parse_prop_items(items)
    assert parsed == {"3149687": {"rush_yd": 100.5, "rec": 4.5}}


def test_back_includes_rush_and_receiving_yards_and_td_odds():
    projection = project_player_props(
        {"rush_yd": 88.5, "rec_yd": 34.5, "rec": 4.5, "anytime_ml": -330},
        {"rush_yd": 0.1, "rec_yd": 0.1, "rec": 1, "rush_td": 6, "rec_td": 6},
        week=3,
        position="RB",
    )
    assert projection is not None
    labels = [row["label"] for row in prop_components(projection.detail)]
    assert labels == ["Rush yds", "Anytime TD", "Rec", "Rec yds"]
    td = next(row for row in prop_components(projection.detail) if row["label"] == "Anytime TD")
    assert td["odds"] == "-330"
    assert td["probability"] == american_probability(-330)
    reasons = explain_projection(projection, on_bye=False, opponent="GB", team="DET", position="RB")
    assert any("Anytime TD -330" in line for line in reasons)


def test_interception_odds_are_devigged():
    from app.nfl_data.market import fair_home_probability

    projection = project_player_props(
        {"pass_yd": 240, "pass_int": 0.5, "pass_int_over": 118, "pass_int_under": -150},
        {"pass_yd": 0.04, "pass_int": -2},
        week=3,
        position="QB",
    )
    assert projection is not None
    row = next(item for item in prop_components(projection.detail) if item["label"] == "INT")
    fair = fair_home_probability(118, -150)
    assert fair is not None
    assert row["probability"] == fair
    assert row["line"] != 0.5
    assert row["odds"] == "+118 / -150"


def test_main_over_under_ignores_alternate_ladders():
    from app.nfl_data.props import parse_dk_board

    rush = parse_dk_board(
        {
            "markets": [{"id": "1", "name": "Jahmyr Gibbs Rushing Yards O/U"}],
            "selections": [
                {
                    "marketId": "1",
                    "outcomeType": "Over",
                    "points": 88.5,
                    "main": True,
                    "displayOdds": {"american": "−110"},
                    "participants": [{"name": "Jahmyr Gibbs"}],
                },
                {
                    "marketId": "1",
                    "outcomeType": "Under",
                    "points": 88.5,
                    "main": True,
                    "displayOdds": {"american": "−114"},
                    "participants": [{"name": "Jahmyr Gibbs"}],
                },
                {
                    "marketId": "1",
                    "label": "100+",
                    "points": None,
                    "main": False,
                    "displayOdds": {"american": "−200"},
                    "participants": [{"name": "Jahmyr Gibbs"}],
                },
            ],
        },
        "rush_yd",
    )
    rec = parse_dk_board(
        {
            "markets": [{"id": "2", "name": "Jahmyr Gibbs Receiving Yards O/U"}],
            "selections": [
                {
                    "marketId": "2",
                    "outcomeType": "Over",
                    "points": 34.5,
                    "main": True,
                    "displayOdds": {"american": "-115"},
                    "participants": [{"name": "Jahmyr Gibbs"}],
                }
            ],
        },
        "rec_yd",
    )
    assert rush["jahmyr gibbs"]["rush_yd"] == 88.5
    assert rec["jahmyr gibbs"]["rec_yd"] == 34.5


def test_recent_game_stats_are_separate_columns():
    game = recent_game(
        week=1,
        raw={"pass_yd": 280, "pass_td": 2, "pts_ppr": 18.2},
        scoring={"pass_yd": 0.04, "pass_td": 4},
        opponent="LV",
        home=False,
    )
    assert game is not None
    assert game.stats == {"pass_yd": 280.0, "pass_td": 2.0}
