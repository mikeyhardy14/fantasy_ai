"""AI Management subs a starter who cannot play and activates a healthy IR player."""

from uuid import uuid4

from sqlalchemy import select

from app.models import Player
from app.schemas.league import PlayerOut, RosterSlotOut, TeamOut, TeamSummaryOut
from app.services.lineup_management import plan_management, sweep_lineup_management
from tests.fixtures import sleeper as fx
from tests.test_sleeper_lineup import TOKEN, _import, _save_token, install_graphql


def _player(name: str, position: str, injury: str | None = None) -> PlayerOut:
    return PlayerOut(
        id=uuid4(),
        name=name,
        position=position,
        fantasy_positions=[position],
        nfl_team="KC",
        injury_status=injury,
    )


def _slot(player: PlayerOut | None, slot: str, index: int | None, starter: bool, flags: list[str]) -> RosterSlotOut:
    return RosterSlotOut(slot=slot, slot_index=index, is_starter=starter, player=player, flags=flags)


def _team(starters, bench, reserve) -> TeamOut:
    return TeamOut(
        team=TeamSummaryOut(
            id=uuid4(), name="Mine", wins=1, losses=0, ties=0, record="1-0", points_for=10, points_against=8
        ),
        week=4,
        starters=starters,
        bench=bench,
        reserve=reserve,
        lineup_slots=[row.slot for row in starters],
        lineup_issues=[],
        projection_coverage="none",
    )


def test_management_subs_an_out_starter_and_activates_a_healthy_ir_player():
    out = _player("Dash Ground", "RB", "Out")
    healthy = _player("Quinn Arrow", "QB")
    backup = _player("Flash Backup", "RB")
    parked = _player("Injured Runner", "RB")
    still_out = _player("Knee Guy", "WR", "Out")
    team = _team(
        [
            _slot(healthy, "QB", 0, True, []),
            _slot(out, "RB", 1, True, ["OUT"]),
        ],
        [_slot(backup, "BN", None, False, [])],
        [
            _slot(parked, "IR", None, False, []),
            _slot(still_out, "IR", None, False, ["OUT"]),
        ],
    )
    moves = plan_management(team)
    assert [(move.player_name, move.destination, move.slot_index) for move in moves] == [
        ("Flash Backup", "starter", 1),
        ("Injured Runner", "bench", None),
    ]
    assert "Dash Ground" in moves[0].summary
    assert "Activate Injured Runner" in moves[1].summary


def test_management_starts_an_ir_player_when_the_bench_cannot_fill_the_spot():
    out = _player("Dash Ground", "RB", "Out")
    parked = _player("Injured Runner", "RB")
    team = _team(
        [_slot(out, "RB", 0, True, ["OUT"])],
        [],
        [_slot(parked, "IR", None, False, [])],
    )
    moves = plan_management(team)
    assert [(move.player_name, move.destination, move.slot_index) for move in moves] == [
        ("Injured Runner", "starter", 0)
    ]


def test_management_leaves_a_questionable_starter():
    shaky = _player("Slot Machine", "WR", "Questionable")
    backup = _player("Bench Receiver", "WR")
    team = _team(
        [_slot(shaky, "WR", 0, True, ["QUESTIONABLE"])],
        [_slot(backup, "BN", None, False, [])],
        [],
    )
    assert plan_management(team) == []


async def test_enabled_management_plans_a_sub_for_an_out_starter(client, auth_headers, sleeper_mock, state):
    install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    blocked = await client.put(
        f"/api/leagues/{league['id']}/management",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert blocked.status_code == 422

    await _save_token(client, auth_headers, TOKEN)
    saved = await client.put(
        f"/api/leagues/{league['id']}/management",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"enabled": True, "available": True}

    async with state.db.session_factory() as session:
        dash = (
            await session.execute(select(Player).where(Player.name == "Dash Ground"))
        ).scalar_one()
        dash.injury_status = "Out"
        await session.commit()

    seen: list[str] = []

    async def apply(_league, move):
        seen.append(move.summary)
        return "saved"

    summaries = await sweep_lineup_management(state, apply=apply)
    assert summaries
    assert any("Flash Backup" in summary and "Dash Ground" in summary for summary in summaries)
    assert seen == summaries
