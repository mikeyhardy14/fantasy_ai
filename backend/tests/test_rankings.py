"""Implied totals, vig-free moneylines, and weekly value over replacement."""

from app.nfl_data.espn import parse_scoreboard
from app.nfl_data.market import BookPrice, american_probability, consensus, fair_home_probability
from app.nfl_data.rankings import RankCandidate, build_rankings, replacement_ranks


def _player(player_id: str, name: str, position: str, points: float, **kwargs) -> RankCandidate:
    return RankCandidate(
        player_id=player_id,
        name=name,
        position=position,
        nfl_team=kwargs.get("team", "KC"),
        opponent=kwargs.get("opponent", "LV"),
        home=kwargs.get("home", True),
        headshot_url=None,
        injury_status=kwargs.get("injury"),
        on_bye=kwargs.get("bye", False),
        ruled_out=kwargs.get("ruled_out", False),
        total=kwargs.get("total", 47.0),
        spread=kwargs.get("spread", -3.0),
        implied_points=kwargs.get("implied", 25.0),
        win_probability=kwargs.get("win", 0.6),
        book_count=kwargs.get("books", 1),
        books=kwargs.get("book_names", ["DraftKings"]),
        projected_points=points,
        projection_source=kwargs.get("source", "vegas"),
    )


def test_home_and_away_implied_points():
    agreed = consensus([BookPrice("DraftKings", home_spread=-3, total=47)])
    assert agreed.home_implied == 25
    assert agreed.away_implied == 22


def test_two_books_are_averaged_and_the_moneyline_is_devigged():
    agreed = consensus(
        [
            BookPrice("DraftKings", home_spread=-3, total=47, home_ml=-150, away_ml=130),
            BookPrice("Pinnacle", home_spread=-5, total=45, home_ml=-150, away_ml=130),
        ]
    )
    assert agreed.book_count == 2
    assert agreed.home_spread == -4
    assert agreed.total == 46
    assert agreed.home_implied == 25
    assert agreed.away_implied == 21
    home = american_probability(-150)
    away = american_probability(130)
    assert home == 0.6
    assert fair_home_probability(-150, 130) == home / (home + away)
    assert agreed.home_win_probability == fair_home_probability(-150, 130)


def test_scoreboard_keeps_one_book_and_reads_the_moneyline():
    games = parse_scoreboard(
        {
            "events": [
                {
                    "competitions": [
                        {
                            "competitors": [
                                {"homeAway": "home", "team": {"abbreviation": "GB"}},
                                {"homeAway": "away", "team": {"abbreviation": "ATL"}},
                            ],
                            "odds": [
                                {
                                    "provider": {"name": "DraftKings"},
                                    "overUnder": 42.5,
                                    "spread": -4.5,
                                    "pointSpread": {
                                        "home": {"close": {"line": "-4.5"}},
                                        "away": {"close": {"line": "+4.5"}},
                                    },
                                    "moneyline": {
                                        "home": {"close": {"odds": "-245"}},
                                        "away": {"close": {"odds": "+200"}},
                                    },
                                }
                            ],
                        }
                    ]
                }
            ]
        },
        3,
    )
    home = games["GB"]
    assert home.books == ["DraftKings"] and home.book_count == 1
    assert home.implied_points == (42.5 - (-4.5)) / 2
    assert home.win_probability == fair_home_probability(-245, 200)
    assert games["ATL"].implied_points == (42.5 + (-4.5)) / 2
    assert games["ATL"].win_probability == 1 - home.win_probability


def test_replacement_splits_flex_between_backs_and_receivers():
    roster = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "IR"]
    ranks = replacement_ranks(12, roster)
    assert ranks == {"QB": 12, "RB": 30, "WR": 30, "TE": 12, "K": 12, "DEF": 12}


def test_value_needs_a_full_replacement_pool_and_skips_bye_and_out():
    roster = ["QB"]
    players = [
        _player("1", "Ace", "QB", 20),
        _player("2", "Bee", "QB", 15),
        _player("3", "Cal", "QB", 11, bye=True),
        _player("4", "Dee", "QB", 9, ruled_out=True, injury="Out"),
    ]
    rows, notes = build_rankings(players, team_count=2, roster_positions=roster)
    assert [row.player.name for row in rows] == ["Ace", "Bee"]
    assert rows[0].vorp == 5
    assert rows[1].vorp == 0
    assert any("QB2" in note for note in notes)
    assert any("not in these ranks" in note for note in notes)
    assert any("DraftKings" in note for note in notes)

    short, short_notes = build_rankings(players[:1], team_count=12, roster_positions=["QB"])
    assert short[0].vorp is None
    assert any("Value is blank" in note for note in short_notes)
