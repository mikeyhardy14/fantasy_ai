"""Sleeper's published weekly points, used when this app has no projection of its own."""

import respx
from httpx import Response

from app.nfl_data.base import PlayerProjection
from app.nfl_data.sleeper_stats import SleeperProjections, index_projections, projection_points
from app.nfl_data.vegas import explain_projection


def test_projection_points_follow_reception_scoring():
    stats = {"pts_ppr": 14.2, "pts_half_ppr": 12.2, "pts_std": 10.2}
    assert projection_points(stats, {"rec": 1}) == (14.2, "Sleeper PPR")
    assert projection_points(stats, {"rec": 0.5}) == (12.2, "Sleeper half PPR")
    assert projection_points(stats, {"rec": 0}) == (10.2, "Sleeper standard")
    assert projection_points(stats, None) == (10.2, "Sleeper standard")


def test_zero_is_a_posted_projection_and_a_missing_column_is_not():
    assert projection_points({"pts_ppr": 0}, {"rec": 1}) == (0.0, "Sleeper PPR")
    assert projection_points({"pts_std": 4}, {"rec": 1})[0] is None
    assert projection_points(None, {"rec": 1})[0] is None
    assert projection_points({"pts_ppr": "nope"}, {"rec": 1})[0] is None


def test_index_projections_keeps_stat_lines_by_player_id():
    indexed = index_projections(
        [
            {},
            {"player_id": 10943, "stats": {"pts_ppr": 0.18}},
            {"player_id": "88", "adp_dd_ppr": 12},
        ]
    )
    assert indexed == {"10943": {"pts_ppr": 0.18}}


def test_sleeper_source_is_named_in_the_explanation():
    projection = PlayerProjection(week=4, points=8.5, source="sleeper")
    reasons = explain_projection(projection, on_bye=False, opponent=None, team="KC", position="WR")
    assert reasons == ["8.5 is Sleeper's projected points for this week."]


@respx.mock
async def test_projections_fetch_strips_v1_and_is_cached(respx_mock, tmp_path):
    route = respx_mock.get("https://api.sleeper.app/projections/nfl/2026/4").mock(
        return_value=Response(200, json=[{"player_id": "7", "stats": {"pts_half_ppr": 9.4}}])
    )
    client = SleeperProjections(tmp_path, "https://api.sleeper.app/v1", ttl_seconds=3600)
    first = await client.player(2026, 4, "7")
    second = await client.player(2026, 4, "7")
    assert first == {"pts_half_ppr": 9.4}
    assert second == first
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.url.params["season_type"] == "regular"
