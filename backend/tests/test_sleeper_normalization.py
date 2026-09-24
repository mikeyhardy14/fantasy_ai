"""Sleeper payload -> normalized DTO mapping (pure functions)."""

from app.providers.sleeper import mappers
from tests.fixtures import sleeper as fx


def test_map_league_details_extracts_settings_and_slots():
    league = mappers.map_league_details(fx.LEAGUE)
    assert league.external_league_id == fx.LEAGUE_ID
    assert league.season == 2026
    assert league.current_week == 4
    assert league.team_count == 2
    assert league.scoring_settings["rec"] == 1.0
    assert league.roster_positions[:3] == ["QB", "RB", "RB"]
    assert league.roster_settings["lineup_slots"] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]
    assert league.roster_settings["bench_slots"] == 2
    assert league.roster_settings["reserve_slots"] == 1
    assert league.league_settings["scoring_type"] == "PPR"
    assert league.league_settings["waiver_type"] == "faab"
    assert league.league_settings["waiver_budget"] == 100


def test_map_league_details_falls_back_to_state_week():
    raw = {**fx.LEAGUE, "settings": {**fx.LEAGUE["settings"], "leg": None}}
    assert mappers.map_league_details(raw, fallback_week=7).current_week == 7


def test_map_league_summary_scoring_type():
    assert mappers.map_league_summary(fx.LEAGUE).scoring_type == "PPR"
    half = {**fx.LEAGUE, "scoring_settings": {"rec": 0.5}}
    assert mappers.map_league_summary(half).scoring_type == "Half PPR"
    std = {**fx.LEAGUE, "scoring_settings": {"rec": 0}}
    assert mappers.map_league_summary(std).scoring_type == "Standard"


def test_map_roster_aligns_starters_with_slots_and_marks_bench_and_ir():
    roster = mappers.map_roster(fx.ROSTERS[0], fx.LEAGUE["roster_positions"])
    by_pid = {e.external_player_id: e for e in roster.entries}
    assert by_pid["1001"].roster_slot == "QB" and by_pid["1001"].is_starter
    assert by_pid["2002"].roster_slot == "RB" and by_pid["2002"].slot_index == 2
    assert by_pid["3003"].roster_slot == "FLEX"
    assert by_pid["KC"].roster_slot == "DEF"
    assert by_pid["2003"].roster_slot == "BN" and not by_pid["2003"].is_starter
    assert by_pid["2004"].roster_slot == "IR"
    assert len(roster.entries) == len(fx.ROSTERS[0]["players"])


def test_map_roster_skips_empty_starter_slots():
    roster = mappers.map_roster(fx.ROSTERS[1], fx.LEAGUE["roster_positions"])
    slots = [e.roster_slot for e in roster.entries if e.is_starter]
    assert "FLEX" not in slots  # "0" placeholder skipped
    assert "0" not in {e.external_player_id for e in roster.entries}


def test_map_teams_merges_users_and_computes_points_and_faab():
    teams = mappers.map_teams(fx.ROSTERS, fx.USERS, waiver_budget=100)
    mine = next(t for t in teams if t.external_team_id == "1")
    assert mine.name == "Mike's Marauders"
    assert mine.owner_external_id == fx.USER_ID
    assert mine.wins == 2 and mine.losses == 1
    assert mine.points_for == 350.55
    assert mine.points_against == 300.10
    assert mine.faab_remaining == 80
    rival = next(t for t in teams if t.external_team_id == "2")
    assert rival.name == "Rival"  # falls back to display_name


def test_map_transaction_normalizes_adds_drops_and_bid():
    tx = mappers.map_transaction(fx.TRANSACTIONS_W3[0])
    assert tx.external_transaction_id == "tx1"
    assert tx.type == "waiver" and tx.status == "complete"
    assert tx.week == 3
    assert tx.adds == [{"external_player_id": "2003", "external_team_id": "1"}]
    assert tx.drops == [{"external_player_id": "9999", "external_team_id": "1"}]
    assert tx.faab_bid == 20
    assert tx.created_at.year == 2025


def test_map_matchup():
    m = mappers.map_matchup(fx.MATCHUPS_W3[0], week=3)
    assert m.external_matchup_id == "1"
    assert m.points == 120.5
    assert m.player_points["1001"] == 22.1
    assert m.projected_points is None


def test_map_player_and_team_defense():
    p = mappers.map_player("3002", fx.PLAYERS["3002"])
    assert p.name == "Slot Machine"
    assert p.injury_status == "Questionable"
    assert p.injury_body_part == "Hamstring"
    assert p.is_fantasy_relevant
    d = mappers.map_player("KC", fx.PLAYERS["KC"])
    assert d.name == "Kansas City Chiefs" and d.position == "DEF"
    retired = mappers.map_player("7001", fx.PLAYERS["7001"])
    assert not retired.is_fantasy_relevant


def test_map_user_and_state():
    u = mappers.map_user(fx.USER)
    assert u.external_user_id == fx.USER_ID and u.username == "mikefantasy"
    assert u.avatar and u.avatar.endswith("abc123")
    s = mappers.map_state(fx.STATE)
    assert (s.season, s.week) == (2026, 4)
