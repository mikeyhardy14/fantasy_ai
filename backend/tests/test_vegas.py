"""Vegas implied points, ESPN scoreboard parsing, and the live data overlay."""

import httpx
import pytest
import respx
from httpx import Response

from app.models import Player, PlayerExternalId
from app.nfl_data.base import player_key
from app.nfl_data.espn import ESPNScheduleClient, SCOREBOARD_URL, SeasonBoard, parse_scoreboard
from app.nfl_data.headshot import headshot_url
from app.nfl_data.live import LiveNFLDataProvider
from app.nfl_data.local_file import LocalFileNFLDataProvider
from app.nfl_data.vegas import implied_team_points, project_from_line


def _event(home: str, away: str, home_line: str, away_line: str, total: float) -> dict:
    return {
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": home}},
                    {"homeAway": "away", "team": {"abbreviation": away}},
                ],
                "odds": [
                    {
                        "overUnder": total,
                        "spread": float(home_line),
                        "pointSpread": {
                            "home": {"close": {"line": home_line}},
                            "away": {"close": {"line": away_line}},
                        },
                    }
                ],
            }
        ]
    }


def _board() -> SeasonBoard:
    week5 = parse_scoreboard(
        {
            "events": [
                _event("DAL", "TB", "-3.5", "+3.5", 47.5),
                _event("JAX", "PHI", "+1.5", "-1.5", 44.0),
                _event("GB", "WSH", "-3", "+3", 42.5),
            ]
        },
        5,
    )
    week6 = parse_scoreboard({"events": [_event("DAL", "PHI", "-7", "+7", 51.0)]}, 6)
    return SeasonBoard({5: week5, 6: week6})


class _StaticEspn:
    def __init__(self, board: SeasonBoard):
        self.board = board

    async def load(self, season: int) -> SeasonBoard:
        return self.board


def test_implied_points_split_the_total():
    assert implied_team_points(47.5, -3.5) == 25.5
    assert implied_team_points(47.5, 3.5) == 22.0


def test_parse_home_dog_and_washington_alias():
    board = _board()
    dal = board.game("DAL", 5)
    assert dal is not None and dal.home is True and dal.opponent == "TB"
    assert dal.spread == -3.5 and dal.implied_points == 25.5
    jax = board.game("JAX", 5)
    assert jax is not None and jax.home is True and jax.spread == 1.5
    assert jax.implied_points == 21.25
    was = board.game("WAS", 5)
    assert was is not None and was.opponent == "GB" and was.home is False
    assert board.game("WSH", 5) is was or board.game("WSH", 5).opponent == "GB"


def test_missing_week_is_a_bye_only_when_the_slate_is_published():
    board = _board()
    tb = board.game("TB", 6)
    assert tb is not None and tb.opponent is None
    assert board.bye_week("TB") == 6
    assert board.bye_week("KC") is None
    assert board.season("TB")[1].opponent is None
    assert board.season("KC") == []


def test_explain_vegas_share_and_missing_line():
    from app.nfl_data.vegas import explain_projection

    qb = project_from_line(week=5, position="QB", depth=1, spread=-3.5, total=47.5, implied=24, scoring={"rec": 1, "pass_td": 4})
    reasons = explain_projection(qb, on_bye=False, opponent="LV", team="KC", position="QB")
    assert any("starting quarterback" in line for line in reasons)
    assert any("72%" in line for line in reasons)
    assert any("against LV" in line for line in reasons)
    missing = explain_projection(None, on_bye=True, opponent=None, team="KC", position="QB")
    assert missing == ["No projection. KC is on bye."]


def test_recent_game_uses_league_scoring():
    from app.nfl_data.sleeper_stats import recent_game

    game = recent_game(
        week=1,
        raw={"rush_yd": 45, "rush_td": 1, "rec": 7, "rec_yd": 48, "fum_lost": 1, "pts_ppr": 20.3},
        scoring={"rush_yd": 0.1, "rush_td": 6, "rec": 1, "rec_yd": 0.1, "fum_lost": -2},
        opponent="BUF",
        home=False,
    )
    assert game is not None
    assert game.fantasy_points == 20.3
    assert game.points_label == "This league"
    assert "45 rush yds" in game.summary
    assert "7 rec" in game.summary
    assert recent_game(week=2, raw={"pos_rank_ppr": 4}, scoring={}, opponent=None, home=None) is None


def test_qb1_and_scoring_and_defense():
    qb = project_from_line(week=5, position="QB", depth=1, spread=-3.5, total=47.5, implied=24, scoring={"rec": 1, "pass_td": 4})
    assert qb is not None and qb.points == 17.3 and qb.source == "vegas"
    wr_ppr = project_from_line(week=5, position="WR", depth=1, spread=-3, total=45, implied=24, scoring={"rec": 1})
    wr_std = project_from_line(week=5, position="WR", depth=1, spread=-3, total=45, implied=24, scoring={"rec": 0})
    assert wr_ppr is not None and wr_std is not None and wr_std.points < wr_ppr.points
    backup = project_from_line(week=5, position="WR", depth=None, spread=-3, total=45, implied=24, scoring={"rec": 1})
    assert backup is not None and backup.points < wr_ppr.points
    defense = project_from_line(week=5, position="DEF", depth=1, spread=3.5, total=47.5, implied=22.0, scoring={})
    assert defense is not None and defense.points == 5.1
    assert project_from_line(week=5, position="WR", depth=1, spread=None, total=None, implied=None, scoring={}) is None


@pytest.mark.asyncio
async def test_local_file_projection_wins_over_vegas(tmp_path):
    path = tmp_path / "nfl.json"
    local = LocalFileNFLDataProvider(path)
    key = player_key("Dak Prescott", "QB", "DAL")
    local.merge({"projections": {"2026": {"5": {key: {"points": 19.4}}}}, "bye_weeks": {"2026": {"TB": 12}}})
    live = LiveNFLDataProvider(local, _StaticEspn(_board()))
    stored = await live.get_projection(key, 2026, 5)
    assert stored is not None and stored.points == 19.4
    vegas = await live.project_from_line(
        nfl_team="DAL", position="QB", depth=1, season=2026, week=5, scoring={"rec": 1, "pass_td": 4}
    )
    assert vegas is not None and vegas.source == "vegas" and vegas.points == round(0.72 * 25.5, 1)
    assert await live.get_opponent("DAL", 2026, 5) == "TB"
    assert await live.get_bye_week("TB", 2026) == 12
    assert await live.project_from_line(
        nfl_team="TB", position="QB", depth=1, season=2026, week=6, scoring={}
    ) is None
    schedule = await live.get_schedule("WAS", 2026)
    assert [g.opponent for g in schedule] == ["GB", None]


def test_headshot_prefers_espn_then_sleeper_then_logo():
    face = Player(name="Dak", position="QB", nfl_team="DAL", extra={"espn_id": "2577417"})
    face.external_ids = [PlayerExternalId(provider="sleeper", external_id="4046")]
    assert headshot_url(face).endswith("/2577417.png")
    thumb = Player(name="Dak", position="QB", nfl_team="DAL", extra={})
    thumb.external_ids = [PlayerExternalId(provider="sleeper", external_id="4046")]
    assert headshot_url(thumb).endswith("/4046.jpg")
    defense = Player(name="Washington", position="DEF", nfl_team="WAS", extra={})
    defense.external_ids = [PlayerExternalId(provider="sleeper", external_id="WAS")]
    assert headshot_url(defense).endswith("/wsh.png")


@pytest.mark.asyncio
@respx.mock
async def test_scoreboard_is_cached(respx_mock, tmp_path):
    def respond(request: httpx.Request) -> Response:
        week = request.url.params.get("week")
        if week == "5":
            return Response(200, json={"events": [_event("DAL", "TB", "-3.5", "+3.5", 47.5)]})
        return Response(200, json={"events": []})

    route = respx_mock.get(SCOREBOARD_URL).mock(side_effect=respond)
    client = ESPNScheduleClient(tmp_path, ttl_seconds=3600)
    first = await client.load(2026)
    second = await client.load(2026)
    assert route.call_count == 18
    assert first.game("DAL", 5).opponent == "TB"
    assert second.game("DAL", 5).opponent == "TB"
    assert (tmp_path / "espn_nfl_2026.json").exists()
