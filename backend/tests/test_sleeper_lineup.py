"""Sleeper scoring-lineup writes. GraphQL is mocked; the public API is the shared fixture."""

import json

from httpx import Response

from tests.conftest import register
from tests.fixtures import sleeper as fx

TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMTEifQ.signaturevalue"


def install_graphql(router, mode: dict):
    seen = {"queries": []}

    def handler(request):
        body = json.loads(request.content)
        query = body["query"]
        seen["queries"].append(query)
        assert "roster_update_starters" not in query
        if "me {" in query:
            assert "email" not in query and "phone" not in query and " token" not in query
            user_id = fx.OPP_USER_ID if mode.get("wrong_user") else fx.USER_ID
            return Response(
                200,
                json={"data": {"me": {"user_id": user_id, "username": "mikefantasy", "display_name": "Mike"}}},
            )
        assert request.headers["authorization"] == TOKEN
        if "roster_update_reserve" in query:
            variables = body["variables"]
            seen["reserve"] = variables["reserve"]
            assert variables["league_id"] == fx.LEAGUE_ID
            assert variables["roster_id"] == 1
            return Response(
                200,
                json={"data": {"roster_update_reserve": {"roster_id": 1, "reserve": variables["reserve"]}}},
            )
        if "update_matchup_leg" in query:
            variables = body["variables"]
            seen["starters"] = variables["starters"]
            assert variables["round"] == variables["leg"] == 4
            assert variables["league_id"] == fx.LEAGUE_ID
            assert variables["roster_id"] == 1
            return Response(200, json={"data": {"update_matchup_leg": {"roster_id": 1, "starters": variables["starters"]}}})
        if "league_rosters" in query:
            reserve = ["999"] if mode.get("reserve_mismatch") else seen.get("reserve", fx.ROSTERS[0]["reserve"])
            return Response(
                200,
                json={
                    "data": {
                        "league_rosters": [
                            {"roster_id": 1, "reserve": reserve, "starters": seen.get("starters", fx.ROSTERS[0]["starters"])},
                            {"roster_id": 2, "reserve": None, "starters": fx.ROSTERS[1]["starters"]},
                        ]
                    }
                },
            )
        if "my_dms" in query:
            return Response(200, json={"data": {"my_dms": mode.get("dms", [])}})
        if "create_dm" in query:
            seen["created_dm"] = body["variables"]
            return Response(200, json={"data": {"create_dm": {"dm_id": "dm-new"}}})
        if "create_message" in query:
            seen["sent"] = body["variables"]
            return Response(200, json={"data": {"create_message": {"message_id": "sent-1"}}})
        if "messages(" in query:
            return Response(200, json={"data": {"messages": mode.get("messages", [])}})
        if "accept_trade" in query or "reject_trade" in query:
            variables = body["variables"]
            seen["respond"] = variables
            seen["respond_op"] = "accept" if "accept_trade" in query else "reject"
            key = "accept_trade" if "accept_trade" in query else "reject_trade"
            return Response(
                200,
                json={"data": {key: {"transaction_id": variables["transaction_id"], "status": "complete" if key == "accept_trade" else "rejected"}}},
            )
        if "propose_trade" in query:
            variables = body["variables"]
            seen["trade"] = variables
            assert variables["league_id"] == fx.LEAGUE_ID
            return Response(
                200,
                json={"data": {"propose_trade": {"transaction_id": "tx-trade", "status": "pending"}}},
            )
        if "league_create_roster_transaction" in query:
            variables = body["variables"]
            seen["add"] = variables["adds"]
            seen["drops"] = variables["drops"]
            assert variables["league_id"] == fx.LEAGUE_ID
            assert variables["roster_id"] == 1
            assert variables["leg"] == 4
            added = variables["adds"][0]["player_id"] if variables["adds"] else None
            return Response(
                200,
                json={
                    "data": {
                        "league_create_roster_transaction": {
                            "transaction_id": "tx-add",
                            "status": "complete",
                            "adds": [{"player_id": added, "roster_id": 1}] if added else [],
                        }
                    }
                },
            )
        if "matchup_legs" in query:
            if mode.get("fail_read"):
                return Response(200, json={"errors": [{"message": "temporarily unavailable"}]})
            starters = fx.ROSTERS[0]["starters"] if mode.get("mismatch") else seen.get("starters")
            return Response(
                200,
                json={
                    "data": {
                        "matchup_legs": [
                            {"roster_id": 1, "starters": starters},
                            {"roster_id": 2, "starters": fx.ROSTERS[1]["starters"]},
                        ]
                    }
                },
            )
        return Response(500, text="unexpected query")

    router.post("https://sleeper.test/graphql").mock(side_effect=handler)
    return seen


async def _import(client, headers):
    from tests.test_integration_flow import import_league

    return await import_league(client, headers)


async def _lineup(client, headers, league_id):
    resp = await client.get(f"/api/leagues/{league_id}/team", headers=headers)
    assert resp.status_code == 200, resp.text
    team = resp.json()
    by_sleeper = {}
    for group in ("starters", "bench", "reserve"):
        for slot in team[group]:
            player = slot["player"]
            if player:
                by_sleeper[player["external_ids"]["sleeper"]] = player["id"]
    starter_ids = [None] * len(team["lineup_slots"])
    for slot in team["starters"]:
        if slot["player"] and slot["slot_index"] is not None:
            starter_ids[slot["slot_index"]] = slot["player"]["id"]
    return team, by_sleeper, starter_ids


async def _save_token(client, headers, token: str = TOKEN):
    return await client.put(
        "/api/integrations/sleeper/token",
        json={"token": f'"{token}"'},
        headers=headers,
    )


async def test_save_token_never_returns_it(client, auth_headers, sleeper_mock):
    install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    saved = await _save_token(client, auth_headers)
    assert saved.status_code == 200, saved.text
    assert TOKEN not in saved.text
    assert saved.json()["writes_enabled"] is True

    listed = await client.get("/api/integrations/accounts", headers=auth_headers)
    assert TOKEN not in listed.text
    assert listed.json()[0]["writes_enabled"] is True

    detail = await client.get(f"/api/leagues/{league['id']}", headers=auth_headers)
    assert TOKEN not in detail.text
    assert detail.json()["account"]["writes_enabled"] is True

    cleared = await client.delete("/api/integrations/sleeper/token", headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["writes_enabled"] is False


async def test_rejects_malformed_and_mismatched_tokens(client, auth_headers, sleeper_mock):
    mode = {}
    install_graphql(sleeper_mock, mode)
    await _import(client, auth_headers)

    bad = await client.put(
        "/api/integrations/sleeper/token",
        json={"token": "this-is-not-a-sleeper-jwt-token"},
        headers=auth_headers,
    )
    assert bad.status_code == 422

    mode["wrong_user"] = True
    wrong = await _save_token(client, auth_headers)
    assert wrong.status_code == 422
    assert "belongs to" in wrong.json()["error"]["message"]
    listed = await client.get("/api/integrations/accounts", headers=auth_headers)
    assert listed.json()[0]["writes_enabled"] is False


async def test_set_lineup_verifies_graphql_and_reports_cached_public_api(client, auth_headers, sleeper_mock):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    _, by_sleeper, starter_ids = await _lineup(client, auth_headers, league["id"])
    starter_ids[6] = by_sleeper["3004"]

    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup",
        json={"week": 4, "starter_player_ids": starter_ids},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["public_api_confirmed"] is False
    assert "cached" in body["message"]
    assert TOKEN not in resp.text
    flex = next(slot for slot in body["team"]["starters"] if slot["slot_index"] == 6)
    assert flex["player"]["external_ids"]["sleeper"] == "3004"
    bench_ids = {slot["player"]["external_ids"]["sleeper"] for slot in body["team"]["bench"]}
    assert "3003" in bench_ids
    assert any("update_matchup_leg" in query for query in seen["queries"])
    assert seen["starters"][6] == "3004"
    assert seen["starters"].count("0") == 0


async def test_unchanged_lineup_is_confirmed_on_the_public_api(client, auth_headers, sleeper_mock):
    install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    _, _, starter_ids = await _lineup(client, auth_headers, league["id"])
    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup",
        json={"week": 4, "starter_player_ids": starter_ids},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verified"] is True
    assert resp.json()["public_api_confirmed"] is True


async def test_scoring_readback_mismatch_does_not_change_the_local_roster(client, auth_headers, sleeper_mock):
    install_graphql(sleeper_mock, {"mismatch": True})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    _, by_sleeper, starter_ids = await _lineup(client, auth_headers, league["id"])
    starter_ids[6] = by_sleeper["3004"]
    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup",
        json={"week": 4, "starter_player_ids": starter_ids},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    flex = next(slot for slot in team["starters"] if slot["slot_index"] == 6)
    assert flex["player"]["external_ids"]["sleeper"] == "3003"


async def test_failed_readback_leaves_the_local_roster_unchanged(client, auth_headers, sleeper_mock):
    install_graphql(sleeper_mock, {"fail_read": True})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    _, by_sleeper, starter_ids = await _lineup(client, auth_headers, league["id"])
    starter_ids[6] = by_sleeper["3004"]
    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup",
        json={"week": 4, "starter_player_ids": starter_ids},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verified"] is None
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    flex = next(slot for slot in team["starters"] if slot["slot_index"] == 6)
    assert flex["player"]["external_ids"]["sleeper"] == "3003"


async def test_lineup_validation_does_not_call_the_mutation(client, auth_headers, sleeper_mock):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    league_id = league["id"]
    _, by_sleeper, starter_ids = await _lineup(client, auth_headers, league_id)

    missing = await client.post(
        f"/api/leagues/{league_id}/lineup",
        json={"week": 4, "starter_player_ids": starter_ids},
        headers=auth_headers,
    )
    assert missing.status_code == 422
    assert "token" in missing.json()["error"]["message"].lower()

    await _save_token(client, auth_headers)
    before = len(seen["queries"])

    wrong_week = await client.post(
        f"/api/leagues/{league_id}/lineup",
        json={"week": 3, "starter_player_ids": starter_ids},
        headers=auth_headers,
    )
    assert wrong_week.status_code == 422

    illegal = starter_ids.copy()
    illegal[1] = by_sleeper["5001"]
    illegal[7] = by_sleeper["2001"]
    ineligible = await client.post(
        f"/api/leagues/{league_id}/lineup",
        json={"week": 4, "starter_player_ids": illegal},
        headers=auth_headers,
    )
    assert ineligible.status_code == 422
    assert "not eligible" in ineligible.json()["error"]["message"]

    reserve = starter_ids.copy()
    reserve[1] = by_sleeper["2004"]
    on_ir = await client.post(
        f"/api/leagues/{league_id}/lineup",
        json={"week": 4, "starter_player_ids": reserve},
        headers=auth_headers,
    )
    assert on_ir.status_code == 422
    assert "IR" in on_ir.json()["error"]["message"]

    assert not any("update_matchup_leg" in query for query in seen["queries"][before:])


async def test_other_user_and_demo_league_cannot_write(client, auth_headers, sleeper_mock):
    install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    other = await register(client, "other@example.com")
    denied = await client.post(
        f"/api/leagues/{league['id']}/lineup",
        json={"week": 4, "starter_player_ids": [None]},
        headers=other,
    )
    assert denied.status_code == 404

    demo = await client.post("/api/demo/league", headers=auth_headers)
    assert demo.status_code == 201, demo.text
    refused = await client.post(
        f"/api/leagues/{demo.json()['id']}/lineup",
        json={"week": demo.json()["current_week"], "starter_player_ids": [None]},
        headers=auth_headers,
    )
    assert refused.status_code == 422
    assert "Sleeper" in refused.json()["error"]["message"]


def _player(team: dict, sleeper_id: str) -> dict:
    for group in ("starters", "bench", "reserve"):
        for slot in team[group]:
            player = slot["player"]
            if player and player["external_ids"]["sleeper"] == sleeper_id:
                return {**player, "slot_index": slot["slot_index"], "group": group}
    raise AssertionError(sleeper_id)


async def test_move_starter_to_bench_only_updates_the_scoring_lineup(client, auth_headers, sleeper_mock):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    player = _player(team, "3003")
    before = len(seen["queries"])

    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": player["id"], "destination": "bench"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["public_api_confirmed"] is False
    assert "bench" in body["message"]
    assert seen["starters"][player["slot_index"]] == "0"
    moved = "".join(seen["queries"][before:])
    assert "update_matchup_leg" in moved
    assert "roster_update_reserve" not in moved
    assert "roster_update_starters" not in moved
    again, _, _ = await _lineup(client, auth_headers, league["id"])
    assert _player(again, "3003")["group"] == "bench"


async def _mark_out(session, sleeper_id: str) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models import League, Player

    players = await session.execute(select(Player).options(selectinload(Player.external_ids)))
    for player in players.scalars():
        if player.external_id_for("sleeper") == sleeper_id:
            player.injury_status = "Out"
    leagues = await session.execute(select(League))
    for league in leagues.scalars():
        league.roster_settings = {**league.roster_settings, "reserve_allow_out": True}
    await session.commit()


async def test_move_between_bench_and_ir(client, auth_headers, sleeper_mock, session):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    await _mark_out(session, "2003")
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    injured = _player(team, "2004")
    before = len(seen["queries"])

    healthy = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": _player(team, "3003")["id"], "destination": "ir"},
        headers=auth_headers,
    )
    assert healthy.status_code == 422
    assert "not eligible" in healthy.json()["error"]["message"]

    full = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": _player(team, "2003")["id"], "destination": "ir"},
        headers=auth_headers,
    )
    assert full.status_code == 422
    assert "full" in full.json()["error"]["message"]
    assert not any("roster_update_reserve" in query for query in seen["queries"][before:])

    off = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": injured["id"], "destination": "bench"},
        headers=auth_headers,
    )
    assert off.status_code == 200, off.text
    assert seen["reserve"] == []
    assert not any("update_matchup_leg" in query for query in seen["queries"][before:])
    benched, _, _ = await _lineup(client, auth_headers, league["id"])
    assert _player(benched, "2004")["group"] == "bench"

    onto = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": _player(benched, "2003")["id"], "destination": "ir"},
        headers=auth_headers,
    )
    assert onto.status_code == 200, onto.text
    assert seen["reserve"] == ["2003"]
    parked, _, _ = await _lineup(client, auth_headers, league["id"])
    assert _player(parked, "2003")["group"] == "reserve"


async def test_move_starter_to_ir_benches_before_reserve(client, auth_headers, sleeper_mock, session):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    await _mark_out(session, "2001")
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": _player(team, "2004")["id"], "destination": "bench"},
        headers=auth_headers,
    )
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    starter = _player(team, "2001")
    before = len(seen["queries"])

    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": starter["id"], "destination": "ir"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    calls = [query for query in seen["queries"][before:] if "mutation" in query or "league_rosters" in query or "matchup_legs" in query]
    lineup_at = next(i for i, query in enumerate(calls) if "update_matchup_leg" in query)
    reserve_at = next(i for i, query in enumerate(calls) if "roster_update_reserve" in query)
    assert lineup_at < reserve_at
    assert seen["starters"][starter["slot_index"]] == "0"
    assert seen["reserve"] == ["2001"]
    moved, _, _ = await _lineup(client, auth_headers, league["id"])
    assert _player(moved, "2001")["group"] == "reserve"


async def test_move_rejects_an_ineligible_slot_without_writing(client, auth_headers, sleeper_mock):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    before = len(seen["queries"])
    resp = await client.post(
        f"/api/leagues/{league['id']}/lineup/move",
        json={"week": 4, "player_id": _player(team, "1001")["id"], "destination": "starter", "slot_index": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "not eligible" in resp.json()["error"]["message"]
    assert len(seen["queries"]) == before


async def test_add_puts_an_unowned_player_on_the_bench(client, auth_headers, sleeper_mock, session):
    from uuid import UUID

    from sqlalchemy import delete

    from app.models import RosterEntry

    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    found = await client.get(
        f"/api/leagues/{league['id']}/players",
        params={"search": "Free", "available": True},
        headers=auth_headers,
    )
    assert found.status_code == 200, found.text
    free = next(player for player in found.json() if player["name"] == "Free Agent")
    full = await client.post(
        f"/api/leagues/{league['id']}/roster/add",
        json={"player_id": free["id"]},
        headers=auth_headers,
    )
    assert full.status_code == 422
    assert "full" in full.json()["error"]["message"]
    assert "add" not in seen

    await session.execute(delete(RosterEntry).where(RosterEntry.player_id == UUID(_player(team, "3004")["id"])))
    await session.commit()
    added = await client.post(
        f"/api/leagues/{league['id']}/roster/add",
        json={"player_id": free["id"]},
        headers=auth_headers,
    )
    assert added.status_code == 200, added.text
    body = added.json()
    assert "Free Agent is on your bench." in body["message"]
    assert body["verified"] is True
    assert seen["add"] == [{"player_id": "6001", "roster_id": 1}]
    assert seen["drops"] == []
    assert any(slot["player"] and slot["player"]["name"] == "Free Agent" for slot in body["team"]["bench"])

    team, _, _ = await _lineup(client, auth_headers, league["id"])
    owned = await client.post(
        f"/api/leagues/{league['id']}/roster/add",
        json={"player_id": _player(team, "1001")["id"]},
        headers=auth_headers,
    )
    assert owned.status_code == 422
    assert "already has" in owned.json()["error"]["message"]


async def test_propose_trade_sends_the_offer_to_one_manager(client, auth_headers, sleeper_mock):
    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    team, by_sleeper, _ = await _lineup(client, auth_headers, league["id"])
    rosters = await client.get(f"/api/leagues/{league['id']}/rosters", headers=auth_headers)
    assert rosters.status_code == 200, rosters.text
    rival = next(row for row in rosters.json() if row["team"]["name"] == "Rival")
    theirs = next(slot["player"]["id"] for slot in rival["starters"] if slot["player"]["external_ids"]["sleeper"] == "2005")

    sent = await client.post(
        f"/api/leagues/{league['id']}/trades",
        json={"give": [by_sleeper["3004"]], "receive": [theirs]},
        headers=auth_headers,
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["opponent_name"] == "Rival"
    assert body["status"] == "pending"
    assert "Bench Receiver" in body["message"]
    assert "Opp RunnerOne" in body["message"]
    assert seen["trade"]["k_drops"] == ["3004", "2005"]
    assert seen["trade"]["k_adds"] == ["2005", "3004"]
    assert seen["trade"]["v_adds"] == [1, 2]
    assert seen["trade"]["v_drops"] == [1, 2]
    assert any(slot["player"] and slot["player"]["name"] == "Bench Receiver" for slot in team["bench"])
    listed = await client.get(f"/api/leagues/{league['id']}/trades", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    offer = next(row for row in listed.json() if row["status"] == "pending")
    assert offer["involves_user"] is True
    user_id = team["team"]["id"]
    assert [player["player_name"] for player in offer["drops"] if player["team_id"] == user_id] == ["Bench Receiver"]
    assert [player["player_name"] for player in offer["adds"] if player["team_id"] == user_id] == ["Opp RunnerOne"]

    mixed = await client.post(
        f"/api/leagues/{league['id']}/trades",
        json={"give": [by_sleeper["3004"]], "receive": [by_sleeper["1001"], theirs]},
        headers=auth_headers,
    )
    assert mixed.status_code == 422


async def test_add_can_drop_someone_or_be_refused(client, auth_headers, sleeper_mock):
    from uuid import uuid4

    seen = install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    team, _, _ = await _lineup(client, auth_headers, league["id"])
    found = await client.get(
        f"/api/leagues/{league['id']}/players",
        params={"search": "Free", "available": True},
        headers=auth_headers,
    )
    free = next(player for player in found.json() if player["name"] == "Free Agent")
    stranger = await client.post(
        f"/api/leagues/{league['id']}/roster/add",
        json={"player_id": free["id"], "drop_player_id": str(uuid4())},
        headers=auth_headers,
    )
    assert stranger.status_code == 422
    assert "not on your roster" in stranger.json()["error"]["message"]
    assert "add" not in seen

    drop_id = _player(team, "3004")["id"]
    added = await client.post(
        f"/api/leagues/{league['id']}/roster/add",
        json={"player_id": free["id"], "drop_player_id": drop_id},
        headers=auth_headers,
    )
    assert added.status_code == 200, added.text
    body = added.json()
    assert "Dropped Bench Receiver." in body["message"]
    assert "Free Agent is on your bench." in body["message"]
    assert seen["drops"] == [{"player_id": "3004", "roster_id": 1}]
    names = [slot["player"]["name"] for group in ("starters", "bench", "reserve") for slot in body["team"][group] if slot["player"]]
    assert "Free Agent" in names
    assert "Bench Receiver" not in names

    flash = next(slot["player"] for slot in body["team"]["bench"] if slot["player"]["name"] == "Flash Backup")
    only_drop = await client.post(
        f"/api/leagues/{league['id']}/roster/add",
        json={"drop_player_id": flash["id"]},
        headers=auth_headers,
    )
    assert only_drop.status_code == 200, only_drop.text
    assert "Dropped Flash Backup." in only_drop.json()["message"]
    assert seen["add"] == []
    assert seen["drops"] == [{"player_id": "2003", "roster_id": 1}]
    left = [
        slot["player"]["name"]
        for group in ("starters", "bench", "reserve")
        for slot in only_drop.json()["team"][group]
        if slot["player"]
    ]
    assert "Flash Backup" not in left


async def test_player_sheet_names_the_team_and_drafts_a_trade(client, auth_headers, sleeper_mock):
    league = await _import(client, auth_headers)
    rosters = await client.get(f"/api/leagues/{league['id']}/rosters", headers=auth_headers)
    assert rosters.status_code == 200, rosters.text
    rows = rosters.json()
    rival = next(row for row in rows if row["team"]["name"] == "Rival")
    target = next(slot["player"] for slot in rival["starters"] if slot["player"]["external_ids"]["sleeper"] == "2005")
    sheet = await client.get(f"/api/leagues/{league['id']}/players/{target['id']}", headers=auth_headers)
    assert sheet.status_code == 200, sheet.text
    assert sheet.json()["rostered_on"]["team_name"] == "Rival"
    assert sheet.json()["rostered_on"]["is_user_team"] is False

    mine = next(row for row in rows if row["team"]["is_user_team"])
    own = next(slot["player"] for slot in mine["starters"] if slot["player"])
    own_sheet = await client.get(f"/api/leagues/{league['id']}/players/{own['id']}", headers=auth_headers)
    assert own_sheet.status_code == 200, own_sheet.text
    assert own_sheet.json()["rostered_on"]["is_user_team"] is True

    draft = await client.post(
        f"/api/leagues/{league['id']}/ai/trade/for",
        json={"player_id": target["id"]},
        headers=auth_headers,
    )
    assert draft.status_code == 200, draft.text
    offer = draft.json()
    assert offer["opponent_name"] == "Rival"
    assert offer["receive"][0]["name"] == "Opp RunnerOne"
    mine_ids = {
        slot["player"]["id"]
        for group in ("starters", "bench", "reserve")
        for slot in mine[group]
        if slot["player"]
    }
    assert offer["give"][0]["id"] in mine_ids
    assert "Opp RunnerOne" in offer["message"]


async def test_league_chat_shows_messages_from_other_managers(client, auth_headers, sleeper_mock):
    install_graphql(
        sleeper_mock,
        {
            "messages": [
                {"message_id": "m2", "created": 1_700_000_000_000, "author_display_name": "Rival", "text": "Nice win", "pinned": False},
                {"message_id": "m1", "created": 1_600_000_000_000, "author_display_name": "Mike", "text": "Good luck", "pinned": True},
                {"message_id": "m3", "created": 1_800_000_000_000, "author_display_name": "Bot", "text": "  ", "pinned": False},
            ]
        },
    )
    league = await _import(client, auth_headers)
    missing = await client.get(f"/api/leagues/{league['id']}/messages", headers=auth_headers)
    assert missing.status_code == 422
    assert "token" in missing.json()["error"]["message"].lower()

    await _save_token(client, auth_headers)
    resp = await client.get(f"/api/leagues/{league['id']}/messages", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [row["author_name"] for row in rows] == ["Mike", "Rival"]
    assert rows[0]["text"] == "Good luck"
    assert rows[0]["pinned"] is True
    assert rows[1]["text"] == "Nice win"


async def test_league_chat_shows_the_players_in_a_proposed_trade(client, auth_headers, sleeper_mock):
    seen = install_graphql(
        sleeper_mock,
        {
            "messages": [
                {
                    "message_id": "t1",
                    "created": 1_700_000_000_000,
                    "author_display_name": "Heater911",
                    "text": "<@Heater911> has proposed a trade in Stud Lite Cup",
                    "attachment": {
                        "type": "transactions",
                        "data": [
                            {
                                "type": "trade",
                                "transaction_id": "9001",
                                "transactions_by_roster": {
                                    "1": {
                                        "status": "pending",
                                        "user": {"display_name": "Heater911", "user_id": fx.USER_ID},
                                        "adds": [{"first_name": "TreVeyon", "last_name": "Henderson", "position": "RB", "player_id": "12529"}],
                                        "drops": [{"first_name": "Quinshon", "last_name": "Judkins", "position": "RB"}],
                                        "added_picks": [{"season": "2027", "round": 2}],
                                    },
                                    "9": {
                                        "status": "pending",
                                        "user": {"display_name": "Rival"},
                                        "adds": [{"first_name": "Quinshon", "last_name": "Judkins", "position": "RB"}],
                                        "drops": [{"first_name": "TreVeyon", "last_name": "Henderson", "position": "RB"}],
                                        "added_picks": [],
                                    },
                                },
                            }
                        ],
                    },
                },
                {
                    "message_id": "t2",
                    "created": 1_700_000_100_000,
                    "author_display_name": "sys",
                    "text": "A trade is now pending.",
                    "attachment": {
                        "type": "transactions",
                        "data": [
                            {
                                "type": "trade",
                                "transaction_id": "9002",
                                "transactions_by_roster": {
                                    "3": {
                                        "status": "pending",
                                        "user": {"display_name": "Other", "user_id": "333"},
                                        "adds": [{"first_name": "A", "last_name": "Player", "position": "WR", "player_id": "1"}],
                                        "drops": [],
                                        "added_picks": [],
                                    },
                                    "4": {
                                        "status": "pending",
                                        "user": {"display_name": "Else", "user_id": "444"},
                                        "adds": [{"first_name": "B", "last_name": "Player", "position": "QB", "player_id": "2"}],
                                        "drops": [],
                                        "added_picks": [],
                                    },
                                },
                            }
                        ],
                    },
                },
            ]
        },
    )
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    resp = await client.get(f"/api/leagues/{league['id']}/messages", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1
    row = resp.json()[0]
    assert "<@" not in row["text"]
    assert row["text"] == "Heater911 offered Quinshon Judkins to Rival for TreVeyon Henderson and 2027 round 2"
    sides = {side["manager"]: side for side in row["trade"]["sides"]}
    assert row["trade"]["involves_user"] is True
    assert row["trade"]["transaction_id"] == "9001"
    assert sides["Heater911"]["receives"][0]["name"] == "TreVeyon Henderson"
    assert sides["Heater911"]["receives"][0]["headshot_url"].endswith("/12529.jpg")
    assert sides["Heater911"]["picks"] == ["2027 round 2"]
    assert sides["Rival"]["receives"][0]["name"] == "Quinshon Judkins"

    stranger = await client.post(
        f"/api/leagues/{league['id']}/trades/9002/respond",
        json={"action": "decline"},
        headers=auth_headers,
    )
    assert stranger.status_code == 422
    assert "respond" not in seen

    accepted = await client.post(
        f"/api/leagues/{league['id']}/trades/9001/respond",
        json={"action": "accept"},
        headers=auth_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert seen["respond_op"] == "accept"
    assert seen["respond"]["transaction_id"] == "9001"
    assert seen["respond"]["league_id"] == fx.LEAGUE_ID
    assert seen["respond"]["leg"] == 4


async def test_direct_chat_is_only_with_managers_in_this_league(client, auth_headers, sleeper_mock):
    seen = install_graphql(
        sleeper_mock,
        {
            "dms": [
                {
                    "dm_id": "dm-rival",
                    "title": None,
                    "dm_type": "single",
                    "last_message_time": 1_700_000_000_000,
                    "recent_users": [
                        {"user_id": fx.USER_ID, "display_name": "MikeFantasy"},
                        {"user_id": fx.OPP_USER_ID, "display_name": "Rival"},
                    ],
                },
                {
                    "dm_id": "dm-stranger",
                    "title": None,
                    "dm_type": "single",
                    "last_message_time": 1_800_000_000_000,
                    "recent_users": [
                        {"user_id": fx.USER_ID, "display_name": "MikeFantasy"},
                        {"user_id": "999", "display_name": "Outsider"},
                    ],
                },
            ],
            "messages": [
                {"message_id": "1", "created": 1_600_000_000_000, "author_id": fx.OPP_USER_ID, "author_display_name": "Rival", "text": "You there?"},
                {"message_id": "2", "created": 1_700_000_000_000, "author_id": fx.USER_ID, "author_display_name": "Mike", "text": "Yeah"},
            ],
        },
    )
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers)
    listed = await client.get(f"/api/leagues/{league['id']}/direct", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    chats = listed.json()
    assert [chat["name"] for chat in chats] == ["Rival"]
    assert chats[0]["thread_id"] == "dm-rival"
    assert chats[0]["team_name"] == "Rival"

    hidden = await client.get(f"/api/leagues/{league['id']}/direct/dm-stranger", headers=auth_headers)
    assert hidden.status_code == 422

    opened = await client.get(f"/api/leagues/{league['id']}/direct/dm-rival", headers=auth_headers)
    assert opened.status_code == 200, opened.text
    assert opened.json()[0]["mine"] is False
    assert opened.json()[1]["mine"] is True
    assert opened.json()[1]["text"] == "Yeah"

    sent = await client.post(
        f"/api/leagues/{league['id']}/direct/dm-rival",
        json={"text": "Trade?"},
        headers=auth_headers,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["thread_id"] == "dm-rival"
    assert seen["sent"]["parent_id"] == "dm-rival"
    assert seen["sent"]["parent_type"] == "dm"
    assert seen["sent"]["text"] == "Trade?"
