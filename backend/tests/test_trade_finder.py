"""Mutual PPG trade finder uses optimal starter totals for both sides."""

from uuid import uuid4

from app.ai.trade_finder import find_mutual_ppg_trades, optimal_starter_ppg
from app.schemas.league import PlayerOut, RosterSlotOut, TeamOut, TeamSummaryOut


def _player(name: str, position: str, ppg: float) -> PlayerOut:
    return PlayerOut(
        id=uuid4(),
        name=name,
        position=position,
        fantasy_positions=[position],
        nfl_team="KC",
        points_per_game=ppg,
        projected_points=ppg,
    )


def _team(name: str, lineup: list[str], starters: list[PlayerOut], bench: list[PlayerOut], *, user=False) -> TeamOut:
    team = TeamSummaryOut(
        id=uuid4(),
        name=name,
        wins=1,
        losses=0,
        ties=0,
        record="1-0",
        points_for=100,
        points_against=90,
        is_user_team=user,
    )
    start_slots = [
        RosterSlotOut(slot=slot, slot_index=index, is_starter=True, player=player)
        for index, (slot, player) in enumerate(zip(lineup, starters, strict=False))
    ]
    # Pad empty starter slots so lineup_slots length matches.
    for index in range(len(starters), len(lineup)):
        start_slots.append(RosterSlotOut(slot=lineup[index], slot_index=index, is_starter=True, player=None))
    bench_slots = [RosterSlotOut(slot="BN", is_starter=False, player=player) for player in bench]
    return TeamOut(
        team=team,
        week=4,
        starters=start_slots,
        bench=bench_slots,
        reserve=[],
        lineup_slots=lineup,
        lineup_issues=[],
        projection_coverage="full",
    )


def test_optimal_starter_ppg_picks_the_best_eligible_players():
    lineup = ["RB", "WR", "FLEX"]
    team = _team(
        "Mine",
        lineup,
        starters=[_player("Starter RB", "RB", 10), _player("Starter WR", "WR", 8)],
        bench=[_player("Bench RB", "RB", 14)],
        user=True,
    )
    # Best lineup is Bench RB (14) + Starter WR (8) + Starter RB in FLEX (10) = 32
    assert optimal_starter_ppg(team) == 32.0


def test_find_mutual_ppg_trades_keeps_swaps_that_help_both_sides():
    lineup = ["RB", "WR"]
    # User is overloaded at RB and thin at WR.
    user = _team(
        "Mine",
        lineup,
        starters=[_player("My RB Ace", "RB", 18), _player("My WR Weak", "WR", 6)],
        bench=[_player("My RB Extra", "RB", 15)],
        user=True,
    )
    # Partner is overloaded at WR and thin at RB.
    partner = _team(
        "Theirs",
        lineup,
        starters=[_player("Their RB Weak", "RB", 7), _player("Their WR Ace", "WR", 17)],
        bench=[_player("Their WR Extra", "WR", 14)],
    )
    trades = find_mutual_ppg_trades(user, [partner], min_gain=0.3)
    assert trades
    best = trades[0]
    assert best.give[0].position == "RB"
    assert best.receive[0].position == "WR"
    assert best.user_delta > 0
    assert best.partner_delta > 0


def test_same_position_downgrade_is_skipped():
    lineup = ["RB"]
    user = _team("Mine", lineup, starters=[_player("Star", "RB", 20)], bench=[], user=True)
    partner = _team("Theirs", lineup, starters=[_player("Backup", "RB", 8)], bench=[])
    assert find_mutual_ppg_trades(user, [partner], min_gain=0.3) == []
