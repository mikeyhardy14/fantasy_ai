"""Completed trades can be reviewed from the league record without submitting anything."""

from datetime import UTC, datetime
from uuid import uuid4

from app.ai.llm import LLMResponse
from app.ai.service import AIService
from app.ai.trade_review import exchanges, format_review, is_trade_review, score_exchange
from app.intelligence.context import TeamContext
from app.schemas.ai import ChatMessageIn, TradeReviewResponse
from app.schemas.league import PlayerOut, RosterNeedsOut, TeamOut, TeamSummaryOut, TransactionOut


def _player(name: str, points: float | None, pid=None) -> PlayerOut:
    return PlayerOut(id=pid or uuid4(), name=name, position="RB", fantasy_positions=["RB"], nfl_team="TB", projected_points=points)


def test_review_requests_are_recognized():
    assert is_trade_review("review the trades that were made")
    assert is_trade_review("What trades were made")
    assert is_trade_review("check the Bucky Irving trade")
    assert is_trade_review("Who should I start at FLEX?") is False
    assert is_trade_review("Should I trade away my kicker?") is False


def test_a_completed_trade_is_scored_for_the_user_without_asking_them_to_submit():
    sent = _player("Bucky Irving", 14.0)
    got = _player("Travis Kelce", 10.0)
    analysis = score_exchange(
        actor="Studs",
        other="Heater",
        give=[sent],
        receive=[got],
        picks=["2027 round 2"],
        yours=True,
        already_done=True,
    )
    assert analysis.verdict == "REJECT"
    assert "You sent Bucky Irving" in analysis.summary
    assert "already on your roster" in analysis.roster_impact[0]
    assert "submit" not in analysis.summary.lower()
    assert "2027 round 2" in analysis.summary


def test_someone_elses_trade_is_not_described_as_yours():
    sides = exchanges(
        adds=[
            {"player_id": "a", "player_name": "Bucky Irving", "team_id": "home", "team_name": "Home"},
            {"player_id": "b", "player_name": "Travis Kelce", "team_id": "away", "team_name": "Away"},
        ],
        drops=[
            {"player_id": "b", "player_name": "Travis Kelce", "team_id": "home", "team_name": "Home"},
            {"player_id": "a", "player_name": "Bucky Irving", "team_id": "away", "team_name": "Away"},
        ],
    )
    assert {row.team_name: [item["player_name"] for item in row.sent] for row in sides} == {
        "Home": ["Travis Kelce"],
        "Away": ["Bucky Irving"],
    }
    analysis = score_exchange(
        actor="Home",
        other="Away",
        give=[_player("Travis Kelce", 10)],
        receive=[_player("Bucky Irving", 16)],
        picks=[],
        yours=False,
        already_done=True,
    )
    review = TradeReviewResponse(
        transaction_id=uuid4(),
        week=2,
        status="complete",
        teams=["Home", "Away"],
        involves_user=False,
        perspective="Home",
        analysis=analysis,
        generated_by="deterministic",
    )
    text = format_review(review)
    assert "Your roster was not in this trade" in text
    assert "You sent" not in text
    assert analysis.verdict == "ACCEPT"


def _trade(user_id, give_id, receive_id) -> TransactionOut:
    return TransactionOut(
        id=uuid4(),
        type="trade",
        status="complete",
        week=2,
        created_at=datetime.now(UTC),
        adds=[
            {"player_id": str(receive_id), "player_name": "Travis Kelce", "team_id": str(user_id), "team_name": "Studs"},
            {"player_id": str(give_id), "player_name": "Bucky Irving", "team_id": "other", "team_name": "Heater"},
        ],
        drops=[
            {"player_id": str(give_id), "player_name": "Bucky Irving", "team_id": str(user_id), "team_name": "Studs"},
            {"player_id": str(receive_id), "player_name": "Travis Kelce", "team_id": "other", "team_name": "Heater"},
        ],
        team_names=["Studs", "Heater"],
        involves_user=True,
    )


async def test_asking_the_assistant_reviews_the_trade_without_calling_the_model():
    user_id = uuid4()
    give = _player("Bucky Irving", 14)
    receive = _player("Travis Kelce", 18)
    trade = _trade(user_id, give.id, receive.id)
    players = {str(give.id): give, str(receive.id): receive}

    class _Service:
        async def league_trades(self, league):
            return [trade]

        async def get_trade(self, league, transaction_id):
            return trade

        async def user_team(self, league):
            return type("Team", (), {"id": user_id, "name": "Studs"})()

        async def get_player_in_league(self, league, player_id, week):
            return players[str(player_id)]

    class _Ctx:
        league = object()
        service = _Service()
        week = 3

        async def team_context(self):
            team = TeamOut(
                team=TeamSummaryOut(
                    id=user_id, name="Studs", wins=1, losses=1, ties=0, record="1-1", points_for=100, points_against=90
                ),
                week=3,
                lineup_slots=["RB"],
                starters=[],
                bench=[],
                reserve=[],
                lineup_issues=[],
                projection_coverage="none",
            )
            return TeamContext(
                league_id="league",
                league_name="Cup",
                season=2026,
                week=3,
                scoring_type="PPR",
                scoring_settings={},
                lineup_slots=["RB"],
                waiver_type=None,
                team=team,
                matchup=None,
                needs=RosterNeedsOut(
                    positions=[],
                    weakest_positions=[],
                    strongest_positions=[],
                    surplus_positions=[],
                    open_roster_spots=0,
                    roster_size=0,
                    max_roster_size=None,
                ),
            )

    llm = type("LLM", (), {"calls": []})()

    async def complete(*args, **kwargs):
        llm.calls.append(kwargs)
        return LLMResponse(content="written", model="fake")

    llm.complete = complete
    resp = await AIService(llm).chat(_Ctx(), [ChatMessageIn(role="user", content="review the trades that were made")])
    assert llm.calls == []
    assert "Travis Kelce" in resp.message
    assert "ACCEPT" in resp.message
    assert resp.generated_by == "deterministic"
