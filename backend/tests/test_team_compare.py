from uuid import uuid4

from app.intelligence.team_compare import comparison_side, comparison_summary
from app.schemas.league import PlayerOut, PositionNeedOut, RosterNeedsOut, RosterSlotOut, TeamOut, TeamSummaryOut


def _team(name: str, record: str, points_for: float, projected: float, starter: PlayerOut, flags: list[str]) -> TeamOut:
    summary = TeamSummaryOut(
        id=uuid4(),
        name=name,
        wins=3,
        losses=1,
        ties=0,
        record=record,
        points_for=points_for,
        points_against=400,
        faab_remaining=80,
    )
    return TeamOut(
        team=summary,
        week=4,
        starters=[RosterSlotOut(slot="RB", slot_index=0, is_starter=True, player=starter, flags=flags)],
        bench=[],
        reserve=[],
        lineup_slots=["RB"],
        lineup_issues=[],
        projected_points=projected,
        projection_coverage="full",
    )


def _needs(position: str, grade: str, healthy: int, total: int) -> RosterNeedsOut:
    return RosterNeedsOut(
        positions=[
            PositionNeedOut(
                position=position,
                required_starters=1,
                healthy_starters=healthy,
                total_depth=total,
                healthy_depth=healthy,
                grade=grade,
            )
        ],
        weakest_positions=[],
        strongest_positions=[],
        surplus_positions=[],
        open_roster_spots=0,
        roster_size=1,
        max_roster_size=15,
    )


def test_comparison_quotes_records_projections_and_the_position_edge():
    alpha = comparison_side(
        _team("Alpha", "4-0", 520.4, 118.2, PlayerOut(id=uuid4(), name="Lead Back", position="RB", nfl_team="KC", projected_points=18.4), []),
        _needs("RB", "Strong", 3, 4),
    )
    beta = comparison_side(
        _team(
            "Beta",
            "2-2",
            410.0,
            96.5,
            PlayerOut(id=uuid4(), name="Hurt Back", position="RB", nfl_team="DAL", projected_points=8.0, injury_status="Out"),
            ["OUT"],
        ),
        _needs("RB", "Weak", 1, 2),
    )
    text = comparison_summary([alpha, beta])
    assert "Alpha is 4-0 with 520.4 points for" in text
    assert "Beta is 2-2 with 410.0 points for" in text
    assert "118.2" in text and "96.5" in text
    assert "ahead at RB" in text
    assert "18.4" in text and "8.0" in text
    assert beta.starters_out == 1
    assert "Beta has 1 starter who cannot play" in text
    assert alpha.positions[0].starter_projection == 18.4
