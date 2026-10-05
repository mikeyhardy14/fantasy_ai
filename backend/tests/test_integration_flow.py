"""End-to-end API flow: register -> connect Sleeper -> import -> dashboard -> sync."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import Matchup, Player, PlayerExternalId, RosterEntry, Transaction
from tests.conftest import register
from tests.fixtures import sleeper as fx


async def import_league(client, headers):
    resp = await client.post("/api/integrations/sleeper/connect", json={"username": "mikefantasy"}, headers=headers)
    assert resp.status_code == 201, resp.text
    resp = await client.post(f"/api/integrations/sleeper/leagues/{fx.LEAGUE_ID}/import", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_auth_register_login_me(client):
    headers = await register(client, "a@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == "a@example.com"

    dup = await client.post("/api/auth/register", json={"email": "a@example.com", "name": "x", "password": "supersecret1"})
    assert dup.status_code == 409

    bad = await client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrongpass1"})
    assert bad.status_code == 401
    ok = await client.post("/api/auth/login", json={"email": "a@example.com", "password": "supersecret1"})
    assert ok.status_code == 200 and ok.json()["access_token"]

    anon = await client.get("/api/leagues")
    assert anon.status_code == 401


async def test_connect_invalid_username(client, auth_headers, sleeper_mock):
    resp = await client.post("/api/integrations/sleeper/connect", json={"username": "nobody_here"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "nobody_here" in resp.json()["error"]["message"]


async def test_connect_rejects_bad_input(client, auth_headers, sleeper_mock):
    resp = await client.post("/api/integrations/sleeper/connect", json={"username": "bad user!"}, headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


async def test_connect_and_list_leagues(client, auth_headers, sleeper_mock):
    resp = await client.post("/api/integrations/sleeper/connect", json={"username": "mikefantasy"}, headers=auth_headers)
    assert resp.status_code == 201
    account = resp.json()
    assert account["provider"] == "sleeper" and account["external_user_id"] == fx.USER_ID

    resp = await client.get("/api/integrations/sleeper/leagues", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["season"] == 2026
    assert body["leagues"][0]["external_league_id"] == fx.LEAGUE_ID
    assert body["leagues"][0]["imported"] is False
    assert body["leagues"][0]["scoring_type"] == "PPR"


async def test_list_leagues_without_account(client, auth_headers, sleeper_mock):
    resp = await client.get("/api/integrations/sleeper/leagues", headers=auth_headers)
    assert resp.status_code == 404


async def test_import_league_and_dashboard(client, auth_headers, sleeper_mock, session):
    league = await import_league(client, auth_headers)
    assert league["name"] == "Test Dynasty League"
    assert league["sync_status"] == "success"
    assert league["user_team_name"] == "Mike's Marauders"
    assert league["current_week"] == 4
    league_id = league["id"]

    # Leagues list marks it imported now
    resp = await client.get("/api/integrations/sleeper/leagues", headers=auth_headers)
    assert resp.json()["leagues"][0]["imported"] is True

    # Team view
    resp = await client.get(f"/api/leagues/{league_id}/team", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    team = resp.json()
    assert team["team"]["record"] == "2-1"
    assert team["team"]["faab_remaining"] == 80
    assert [s["slot"] for s in team["starters"]] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]
    assert {s["player"]["name"] for s in team["bench"]} == {"Flash Backup", "Bench Receiver"}
    assert team["reserve"][0]["player"]["name"] == "Injured Runner"
    wr2 = next(s for s in team["starters"] if s["player"]["name"] == "Slot Machine")
    assert "QUESTIONABLE" in wr2["flags"]
    assert team["projection_coverage"] == "none"  # no NFL data configured

    # Matchup
    resp = await client.get(f"/api/leagues/{league_id}/matchup", headers=auth_headers)
    m = resp.json()
    assert m["week"] == 4 and m["opponent"]["team"]["name"] == "Rival" and m["status"] == "upcoming"
    resp = await client.get(f"/api/leagues/{league_id}/matchup?week=3", headers=auth_headers)
    past = resp.json()
    assert past["user"]["points"] == 120.5 and past["status"] == "final"
    flex = next(slot for slot in past["user"]["starters"] if slot["slot"] == "FLEX")
    assert flex["player"]["name"] == "Flash Backup"

    # League detail with settings
    resp = await client.get(f"/api/leagues/{league_id}", headers=auth_headers)
    detail = resp.json()
    assert detail["scoring_settings"]["rec"] == 1.0
    assert detail["roster_settings"]["lineup_slots"][0] == "QB"

    # Available players excludes rostered + irrelevant players
    resp = await client.get(f"/api/leagues/{league_id}/players", headers=auth_headers)
    names = {p["name"] for p in resp.json()}
    assert {"Free Agent", "Waiver Wire", "Spare Tight"} <= names
    assert "Quinn Arrow" not in names
    assert "Old Timer" not in names
    resp = await client.get(f"/api/leagues/{league_id}/players?position=te", headers=auth_headers)
    assert [p["name"] for p in resp.json()] == ["Spare Tight"]

    # Standings + transactions
    resp = await client.get(f"/api/leagues/{league_id}/standings", headers=auth_headers)
    assert resp.json()[0]["name"] == "Mike's Marauders" and resp.json()[0]["rank"] == 1
    resp = await client.get(f"/api/leagues/{league_id}/transactions", headers=auth_headers)
    tx = resp.json()[0]
    assert tx["type"] == "waiver" and tx["adds"][0]["player_name"] == "Flash Backup" and tx["involves_user"]
    assert tx["adds"][0]["headshot_url"].endswith("/2003.jpg")
    assert tx["drops"][0]["headshot_url"].endswith("/9999.jpg")

    # Player mapping: internal id != Sleeper id, mapping table holds the Sleeper id
    result = await session.execute(
        select(Player).join(PlayerExternalId).where(PlayerExternalId.external_id == "1001")
    )
    player = result.scalar_one()
    assert str(player.id) != "1001"
    assert player.external_id_for("sleeper") == "1001"
    assert player.external_id_for("yahoo") is None
    # Dropped player referenced only by a transaction still persisted so the link resolves.
    assert tx["drops"][0]["player_name"] == "Dropped Guy"


async def test_opening_a_league_reads_sleeper_live(client, auth_headers, sleeper_mock):
    from copy import deepcopy

    from httpx import Response

    league = await import_league(client, auth_headers)
    rosters = deepcopy(fx.ROSTERS)
    rosters[0]["settings"]["wins"] = 9
    rosters[0]["starters"] = ["2003", *rosters[0]["starters"][1:]]
    sleeper_mock.get(f"/league/{fx.LEAGUE_ID}/rosters").mock(return_value=Response(200, json=rosters))

    resp = await client.get(f"/api/leagues/{league['id']}/team", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["team"]["wins"] == 9
    assert body["starters"][0]["player"]["name"] == "Flash Backup"


async def test_sync_is_idempotent(client, auth_headers, sleeper_mock, session):
    league = await import_league(client, auth_headers)
    league_id = league["id"]

    async def counts():
        out = {}
        for model in (Player, PlayerExternalId, RosterEntry, Matchup, Transaction):
            out[model.__name__] = (await session.execute(select(func.count()).select_from(model))).scalar_one()
        return out

    first = await counts()
    assert first["RosterEntry"] == (12 + 8) * 2  # current week plus week 3 matchup lineups
    assert first["Matchup"] == 4  # week 3 + week 4, two teams each
    assert first["Transaction"] == 1

    resp = await client.post(f"/api/leagues/{league_id}/sync", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["league"]["sync_status"] == "success"
    # Re-import through the integrations endpoint should also be a no-op on counts.
    resp = await client.post(f"/api/integrations/sleeper/leagues/{fx.LEAGUE_ID}/import", headers=auth_headers)
    assert resp.status_code == 200
    assert await counts() == first

    resp = await client.get("/api/leagues", headers=auth_headers)
    assert len(resp.json()) == 1


async def test_sync_failure_records_error(client, auth_headers, sleeper_mock):
    from httpx import Response

    league = await import_league(client, auth_headers)
    sleeper_mock.get(f"/league/{fx.LEAGUE_ID}/rosters").mock(return_value=Response(500))
    resp = await client.post(f"/api/leagues/{league['id']}/sync", headers=auth_headers)
    assert resp.status_code == 502
    resp = await client.get(f"/api/leagues/{league['id']}", headers=auth_headers)
    assert resp.json()["sync_status"] == "error"
    assert resp.json()["sync_error"]


async def test_import_unknown_league(client, auth_headers, sleeper_mock):
    await client.post("/api/integrations/sleeper/connect", json={"username": "mikefantasy"}, headers=auth_headers)
    resp = await client.post("/api/integrations/sleeper/leagues/000/import", headers=auth_headers)
    assert resp.status_code == 404


async def test_import_all_leagues(client, auth_headers, sleeper_mock):
    fx.install_extra_league(sleeper_mock)
    await client.post("/api/integrations/sleeper/connect", json={"username": "mikefantasy"}, headers=auth_headers)

    listed = await client.get("/api/integrations/sleeper/leagues", headers=auth_headers)
    assert [lg["name"] for lg in listed.json()["leagues"]] == ["Test Dynasty League", "Test Redraft League"]
    assert all(not lg["imported"] for lg in listed.json()["leagues"])

    resp = await client.post("/api/integrations/sleeper/leagues/import-all", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    imported = resp.json()
    assert {lg["name"] for lg in imported} == {"Test Dynasty League", "Test Redraft League"}
    assert all(lg["sync_status"] == "success" for lg in imported)

    again = await client.post("/api/integrations/sleeper/leagues/import-all", headers=auth_headers)
    assert again.status_code == 200
    assert again.json() == []

    listed = await client.get("/api/integrations/sleeper/leagues", headers=auth_headers)
    assert all(lg["imported"] for lg in listed.json()["leagues"])
    owned = await client.get("/api/leagues", headers=auth_headers)
    assert {lg["external_league_id"] for lg in owned.json()} == {fx.LEAGUE_ID, fx.LEAGUE_ID_2}


async def test_import_all_skips_leagues_already_imported(client, auth_headers, sleeper_mock):
    fx.install_extra_league(sleeper_mock)
    first = await import_league(client, auth_headers)
    resp = await client.post("/api/integrations/sleeper/leagues/import-all", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    remaining = resp.json()
    assert len(remaining) == 1
    assert remaining[0]["name"] == "Test Redraft League"
    assert remaining[0]["id"] != first["id"]


async def test_league_authorization(client, auth_headers, sleeper_mock):
    league = await import_league(client, auth_headers)
    other = await register(client, "other@example.com", "Other")
    for path in ("", "/team", "/matchup", "/players", "/standings", "/transactions", "/recommendations", "/briefing"):
        resp = await client.get(f"/api/leagues/{league['id']}{path}", headers=other)
        assert resp.status_code == 404, path
    resp = await client.post(f"/api/leagues/{league['id']}/sync", headers=other)
    assert resp.status_code == 404
    resp = await client.post(f"/api/leagues/{league['id']}/ai/analyze", headers=other)
    assert resp.status_code == 404
    resp = await client.get("/api/leagues", headers=other)
    assert resp.json() == []
    resp = await client.get(f"/api/leagues/{uuid4()}/team", headers=auth_headers)
    assert resp.status_code == 404


async def test_matchup_nfl_games_follow_the_requested_week(client, auth_headers, sleeper_mock, state):
    from app.nfl_data.espn import GameSummary

    class WeekSlate:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        async def live_summaries(self, season, week):
            done = week < 4
            return [
                GameSummary(
                    away="BUF" if week == 3 else "SF",
                    home="KC",
                    away_score=14 if done else None,
                    home_score=21 if done else None,
                    state="post" if done else "pre",
                    detail="Final" if done else "Sun 1:00 PM",
                    summary=None,
                    broadcast="CBS",
                )
            ]

    state.nfl_data = WeekSlate(state.nfl_data)
    league = await import_league(client, auth_headers)
    league_id = league["id"]

    past = (await client.get(f"/api/leagues/{league_id}/matchup?week=3", headers=auth_headers)).json()
    assert past["games"][0]["away"] == "BUF"
    assert past["games"][0]["state"] == "post"
    flex = next(slot for slot in past["user"]["starters"] if slot["slot"] == "FLEX")
    assert flex["player"]["name"] == "Flash Backup"

    current = (await client.get(f"/api/leagues/{league_id}/matchup?week=4", headers=auth_headers)).json()
    assert current["games"][0]["away"] == "SF"
    assert current["games"][0]["state"] == "pre"
    flex = next(slot for slot in current["user"]["starters"] if slot["slot"] == "FLEX")
    assert flex["player"]["name"] == "Deep Threat"

    future = (await client.get(f"/api/leagues/{league_id}/matchup?week=5", headers=auth_headers)).json()
    assert future["games"][0]["away"] == "SF"
    assert future["is_bye"] is True


@pytest.mark.parametrize("provider", ["yahoo", "espn", "nfl"])
async def test_stub_providers_declare_capabilities(client, provider):
    resp = await client.get("/api/integrations/providers")
    entry = next(p for p in resp.json() if p["provider"] == provider)
    assert entry["implemented"] is False
    assert entry["capabilities"]["auth_type"] in ("oauth", "cookie")
