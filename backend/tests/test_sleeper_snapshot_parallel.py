"""League snapshot pulls matchup/transaction weeks concurrently on one client."""

import httpx
import pytest
import respx
from httpx import Response

from app.providers.sleeper import SleeperClient, SleeperProvider

BASE = "https://sleeper.test/v1"

LEAGUE = {
    "league_id": "L1",
    "name": "Test",
    "season": "2026",
    "status": "in_season",
    "total_rosters": 2,
    "roster_positions": ["QB", "RB", "WR", "TE", "BN"],
    "scoring_settings": {"rec": 1},
    "settings": {"leg": 4, "waiver_budget": 100},
}


def _roster(roster_id: int, owner: str) -> dict:
    return {
        "roster_id": roster_id,
        "owner_id": owner,
        "players": ["1"],
        "starters": ["1"],
        "reserve": [],
        "settings": {"wins": 1, "losses": 0, "ties": 0, "fpts": 10, "fpts_against": 8},
    }


@respx.mock(base_url=BASE)
async def test_fetch_league_snapshot_parallel_weeks(respx_mock, tmp_path):
    respx_mock.get("/league/L1").mock(return_value=Response(200, json=LEAGUE))
    respx_mock.get("/league/L1/rosters").mock(
        return_value=Response(200, json=[_roster(1, "u1"), _roster(2, "u2")])
    )
    respx_mock.get("/league/L1/users").mock(
        return_value=Response(
            200,
            json=[
                {"user_id": "u1", "display_name": "A", "metadata": {"team_name": "A"}},
                {"user_id": "u2", "display_name": "B", "metadata": {"team_name": "B"}},
            ],
        )
    )
    respx_mock.get("/players/nfl").mock(
        return_value=Response(200, json={"1": {"player_id": "1", "full_name": "Test", "position": "RB"}})
    )
    for week in (1, 2, 3, 4, 5):
        respx_mock.get(f"/league/L1/matchups/{week}").mock(
            return_value=Response(
                200,
                json=[
                    {"roster_id": 1, "matchup_id": 1, "points": 10, "starters": ["1"], "players_points": {"1": 10}},
                    {"roster_id": 2, "matchup_id": 1, "points": 8, "starters": ["1"], "players_points": {"1": 8}},
                ],
            )
        )
    for week in (1, 2, 3, 4):
        respx_mock.get(f"/league/L1/transactions/{week}").mock(return_value=Response(200, json=[]))

    client = SleeperClient(base_url=BASE, timeout=1.0, max_retries=0, player_cache_path=tmp_path / "p.json")
    snapshot = await SleeperProvider(client).fetch_league_snapshot("L1", weeks_back=3, weeks_forward=1)
    assert snapshot.league.current_week == 4
    assert len(snapshot.matchups) == 10  # 5 weeks × 2 sides
    assert client._http is not None and not client._http.is_closed
    await client.aclose()
