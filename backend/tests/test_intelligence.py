"""Deterministic engine: eligibility, lineup issues, swaps, roster needs."""

from uuid import uuid4

from app.intelligence.lineup import is_eligible, lineup_issues, player_flags, suggest_swaps
from app.intelligence.roster_needs import compute_roster_needs
from app.schemas.league import PlayerOut, RosterSlotOut

LINEUP = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]


def player(name, pos, injury=None, bye=None, proj=None, team="KC", positions=None) -> PlayerOut:
    return PlayerOut(
        id=uuid4(), name=name, position=pos, fantasy_positions=positions or [pos], nfl_team=team,
        injury_status=injury, bye_week=bye, on_bye=bye == 4, projected_points=proj,
    )


def slot(p: PlayerOut, slot_name: str, starter: bool = True, idx: int | None = None) -> RosterSlotOut:
    return RosterSlotOut(slot=slot_name, slot_index=idx, is_starter=starter, player=p, flags=player_flags(p, week=4))


def test_slot_eligibility():
    assert is_eligible(player("A", "RB"), "FLEX")
    assert is_eligible(player("A", "TE"), "FLEX")
    assert not is_eligible(player("A", "QB"), "FLEX")
    assert is_eligible(player("A", "QB"), "SUPER_FLEX")
    assert not is_eligible(player("A", "WR"), "RB")
    assert is_eligible(player("A", "RB", positions=["RB", "WR"]), "WR")
    assert is_eligible(player("A", "QB"), "BN")


def test_flags():
    assert "BYE" in player_flags(player("A", "RB", bye=4), 4)
    assert "OUT" in player_flags(player("A", "RB", injury="Out"), 4)
    assert "IR" in player_flags(player("A", "RB", injury="IR"), 4)
    assert "QUESTIONABLE" in player_flags(player("A", "RB", injury="Questionable"), 4)
    assert player_flags(player("A", "RB"), 4) == []


def test_lineup_issues_detects_empty_ineligible_bye_and_out():
    starters = [
        slot(player("QB1", "QB"), "QB", idx=0),
        slot(player("RB1", "RB", injury="Out"), "RB", idx=1),
        slot(player("WR-in-RB", "WR"), "RB", idx=2),
        slot(player("TE-bye", "TE", bye=4), "TE", idx=5),
    ]
    issues = lineup_issues(starters, LINEUP)
    assert any("WR slot is empty" in i for i in issues)
    assert any("not eligible for RB" in i for i in issues)
    assert any("on bye" in i for i in issues)
    assert any("RB1 (RB) is Out" in i for i in issues)


def test_suggest_swaps_prefers_replacing_unavailable_starters():
    starters = [slot(player("Bye TE", "TE", bye=4, proj=0), "TE", idx=5), slot(player("Healthy RB", "RB", proj=15), "RB", idx=1)]
    bench = [slot(player("Backup TE", "TE", proj=8), "BN", starter=False), slot(player("Bench RB", "RB", proj=9), "BN", starter=False)]
    swaps = suggest_swaps(starters, bench)
    assert len(swaps) == 1
    assert swaps[0].slot == "TE" and swaps[0].replacement.player.name == "Backup TE" and swaps[0].urgency == "HIGH"


def test_suggest_swaps_projection_upgrade_and_threshold():
    starters = [slot(player("Starter", "WR", proj=10.0), "FLEX", idx=6)]
    bench = [slot(player("Better", "RB", proj=13.5), "BN", starter=False), slot(player("Slightly", "WR", proj=11.0), "BN", starter=False)]
    swaps = suggest_swaps(starters, bench)
    assert len(swaps) == 1 and swaps[0].replacement.player.name == "Better" and swaps[0].projection_delta == 3.5


def test_suggest_swaps_without_projections_only_uses_availability():
    starters = [slot(player("Healthy", "WR"), "WR", idx=3)]
    bench = [slot(player("Also healthy", "WR"), "BN", starter=False)]
    assert suggest_swaps(starters, bench) == []


def test_roster_needs_grades():
    roster = [
        slot(player("QB1", "QB"), "QB"),
        slot(player("RB1", "RB"), "RB"), slot(player("RB2", "RB", injury="Out"), "RB"),
        slot(player("WR1", "WR"), "WR"), slot(player("WR2", "WR"), "WR"), slot(player("WR3", "WR"), "FLEX"),
        slot(player("TE1", "TE"), "TE"),
        slot(player("K1", "K"), "K"), slot(player("D1", "DEF"), "DEF"),
        slot(player("WR4", "WR"), "BN", starter=False), slot(player("WR5", "WR"), "BN", starter=False), slot(player("WR6", "WR"), "BN", starter=False),
        slot(player("QB2", "QB"), "BN", starter=False),
    ]
    needs = compute_roster_needs(LINEUP, roster, max_roster_size=15)
    by_pos = {p.position: p for p in needs.positions}
    assert by_pos["RB"].grade == "Weak"  # 1 healthy for 2 slots
    assert by_pos["WR"].grade == "Strong"
    assert by_pos["QB"].grade == "Strong"
    assert by_pos["TE"].grade == "Needs depth"
    assert by_pos["K"].grade == "Adequate"
    assert "RB" in needs.weakest_positions
    assert "WR" in needs.surplus_positions
    assert needs.roster_size == 13 and needs.open_roster_spots == 2
