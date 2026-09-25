"""Sub requests become lineup buttons. They do not write until the button is used."""

from uuid import uuid4

from app.ai.approvals import swaps_mentioned
from app.ai.llm import LLMResponse
from app.ai.service import AIService
from app.ai.subs import sub_proposal
from app.schemas.ai import ChatMessageIn
from app.schemas.league import PlayerOut, RosterSlotOut, TeamOut, TeamSummaryOut


def _player(name: str, position: str, points: float | None = None) -> PlayerOut:
    return PlayerOut(
        id=uuid4(),
        name=name,
        position=position,
        fantasy_positions=[position],
        nfl_team="BAL",
        projected_points=points,
    )


def _slot(player: PlayerOut, slot: str, index: int | None, starter: bool, flags: list[str] | None = None) -> RosterSlotOut:
    return RosterSlotOut(slot=slot, slot_index=index, is_starter=starter, player=player, flags=flags or [])


def _team() -> TeamOut:
    lamar = _player("Lamar Jackson", "QB", 22.3)
    backup = _player("Cooper Rush", "QB", 8.1)
    hurts = _player("Jalen Hurts", "QB", 4.0)
    return TeamOut(
        team=TeamSummaryOut(id=uuid4(), name="Studs", wins=2, losses=0, ties=0, record="2-0", points_for=200, points_against=180),
        week=3,
        lineup_slots=["QB", "RB"],
        starters=[_slot(lamar, "QB", 0, True), _slot(_player("Saquon Barkley", "RB", 18), "RB", 1, True)],
        bench=[_slot(backup, "BN", None, False), _slot(hurts, "BN", None, False)],
        reserve=[],
        lineup_issues=[],
        projection_coverage="partial",
    )


class _Ctx:
    async def team_context(self):
        from app.intelligence.context import TeamContext
        from app.schemas.league import RosterNeedsOut

        team = _team()
        return TeamContext(
            league_id="league",
            league_name="Cup",
            season=2026,
            week=3,
            scoring_type="PPR",
            scoring_settings={},
            lineup_slots=team.lineup_slots,
            waiver_type=None,
            team=team,
            matchup=None,
            needs=RosterNeedsOut(
                positions=[],
                weakest_positions=[],
                strongest_positions=[],
                surplus_positions=[],
                open_roster_spots=0,
                roster_size=4,
                max_roster_size=None,
            ),
        )


def test_subbing_a_starter_lists_eligible_backups_highest_first():
    message, actions = sub_proposal(_team(), 3, "sub Lamar Jackson")
    assert "starting at QB" in message
    assert [action.player_name for action in actions] == ["Cooper Rush", "Jalen Hurts"]
    assert actions[0].slot_index == 0
    assert actions[0].destination == "starter"
    assert actions[0].replaces == "Lamar Jackson"
    assert actions[0].label == "Sub in Cooper Rush"
    assert actions[0].week == 3
    assert actions[0].summary.startswith("Start Cooper Rush over Lamar Jackson at QB.")


def test_sub_for_names_the_one_move():
    message, actions = sub_proposal(_team(), 3, "sub Cooper Rush for Lamar")
    assert actions[0].player_name == "Cooper Rush"
    assert actions[0].replaces == "Lamar Jackson"
    assert "Cooper Rush" in message and "Lamar Jackson" in message


def test_subbing_a_bench_player_offers_the_starter_he_replaces():
    _, actions = sub_proposal(_team(), 3, "sub in Cooper Rush")
    assert len(actions) == 1
    assert actions[0].label == "Start over Lamar Jackson"
    assert actions[0].player_name == "Cooper Rush"
    assert actions[0].slot == "QB"


def test_a_normal_question_is_not_a_sub():
    assert sub_proposal(_team(), 3, "Who should I start at FLEX?") is None


def test_saying_start_over_becomes_one_approval():
    actions = swaps_mentioned(_team(), 3, "Start Cooper Rush over Lamar Jackson at QB.")
    assert len(actions) == 1
    assert actions[0].player_name == "Cooper Rush"
    assert actions[0].replaces == "Lamar Jackson"
    assert actions[0].slot_index == 0
    assert "8.1 projected" in actions[0].summary
    assert "22.3 projected" in actions[0].summary


def test_telling_the_manager_not_to_start_over_is_not_an_approval():
    assert swaps_mentioned(_team(), 3, "Do not start Cooper Rush over Lamar Jackson.") == []


async def test_sub_request_does_not_call_the_model():
    llm = type("LLM", (), {"model": "fake", "calls": [], "complete": None})()
    llm.calls = []

    async def complete(*args, **kwargs):
        llm.calls.append(kwargs)
        return LLMResponse(content="written", model="fake")

    llm.complete = complete
    service = AIService(llm)
    resp = await service.chat(_Ctx(), [ChatMessageIn(role="user", content="sub Lamar Jackson")])
    assert resp.actions
    assert resp.actions[0].player_name == "Cooper Rush"
    assert llm.calls == []
