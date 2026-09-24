"""Realistic Sleeper API payloads for tests (2 teams to keep them small)."""

from httpx import Response

USER_ID = "111111111111111111"
OPP_USER_ID = "222222222222222222"
LEAGUE_ID = "999999999999999999"

STATE = {"season": "2026", "week": 4, "display_week": 4, "season_type": "regular", "league_season": "2026"}

USER = {"user_id": USER_ID, "username": "mikefantasy", "display_name": "MikeFantasy", "avatar": "abc123"}

LEAGUE = {
    "league_id": LEAGUE_ID,
    "name": "Test Dynasty League",
    "season": "2026",
    "status": "in_season",
    "total_rosters": 2,
    "avatar": None,
    "draft_id": "draft1",
    "previous_league_id": None,
    "settings": {
        "leg": 4,
        "num_teams": 2,
        "waiver_type": 2,
        "waiver_budget": 100,
        "reserve_slots": 1,
        "taxi_slots": 0,
        "playoff_week_start": 15,
        "playoff_teams": 6,
        "trade_deadline": 12,
        "type": 0,
    },
    "scoring_settings": {"rec": 1.0, "pass_td": 4.0, "rush_td": 6.0, "rec_td": 6.0, "pass_yd": 0.04, "rush_yd": 0.1, "rec_yd": 0.1},
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "IR"],
}

LEAGUES = [LEAGUE]

USERS = [
    {"user_id": USER_ID, "display_name": "MikeFantasy", "avatar": None, "metadata": {"team_name": "Mike's Marauders"}},
    {"user_id": OPP_USER_ID, "display_name": "Rival", "avatar": None, "metadata": {}},
]

# Player ids: strings like Sleeper. "KC" is a team defense.
ROSTERS = [
    {
        "roster_id": 1,
        "owner_id": USER_ID,
        "league_id": LEAGUE_ID,
        "starters": ["1001", "2001", "2002", "3001", "3002", "4001", "3003", "5001", "KC"],
        "players": ["1001", "2001", "2002", "2003", "3001", "3002", "3003", "3004", "4001", "5001", "KC", "2004"],
        "reserve": ["2004"],
        "taxi": None,
        "settings": {"wins": 2, "losses": 1, "ties": 0, "fpts": 350, "fpts_decimal": 55, "fpts_against": 300, "fpts_against_decimal": 10, "waiver_budget_used": 20, "waiver_position": 5, "total_moves": 3},
    },
    {
        "roster_id": 2,
        "owner_id": OPP_USER_ID,
        "league_id": LEAGUE_ID,
        "starters": ["1002", "2005", "2006", "3005", "3006", "4002", "0", "5002", "BUF"],
        "players": ["1002", "2005", "2006", "3005", "3006", "4002", "5002", "BUF"],
        "reserve": None,
        "taxi": None,
        "settings": {"wins": 1, "losses": 2, "ties": 0, "fpts": 301, "fpts_decimal": 0, "fpts_against": 320, "waiver_budget_used": 0, "waiver_position": 1},
    },
]

MATCHUPS_W4 = [
    {"matchup_id": 1, "roster_id": 1, "points": 0.0, "players_points": {}, "starters": ROSTERS[0]["starters"]},
    {"matchup_id": 1, "roster_id": 2, "points": 0.0, "players_points": {}, "starters": ROSTERS[1]["starters"]},
]
MATCHUPS_W3 = [
    {"matchup_id": 1, "roster_id": 1, "points": 120.5, "players_points": {"1001": 22.1, "2001": 18.4}},
    {"matchup_id": 1, "roster_id": 2, "points": 99.2, "players_points": {"1002": 15.0}},
]

TRANSACTIONS_W3 = [
    {
        "transaction_id": "tx1",
        "type": "waiver",
        "status": "complete",
        "roster_ids": [1],
        "adds": {"2003": 1},
        "drops": {"9999": 1},
        "settings": {"waiver_bid": 20, "seq": 1},
        "created": 1758000000000,
        "status_updated": 1758000000000,
        "leg": 3,
        "creator": USER_ID,
        "metadata": {"notes": None},
        "draft_picks": [],
        "waiver_budget": [],
    }
]


def _p(pid, first, last, pos, team, status="Active", injury=None, fantasy_positions=None, body=None):
    return {
        "player_id": pid,
        "first_name": first,
        "last_name": last,
        "full_name": f"{first} {last}" if pos != "DEF" else None,
        "position": pos,
        "fantasy_positions": fantasy_positions or [pos],
        "team": team,
        "status": status,
        "injury_status": injury,
        "injury_body_part": body,
        "age": 27,
        "years_exp": 4,
        "number": 10,
        "active": True,
    }


PLAYERS = {
    "1001": _p("1001", "Quinn", "Arrow", "QB", "KC"),
    "1002": _p("1002", "Rex", "Cannon", "QB", "BUF"),
    "2001": _p("2001", "Dash", "Ground", "RB", "SF"),
    "2002": _p("2002", "Bruno", "Trucks", "RB", "DET"),
    "2003": _p("2003", "Flash", "Backup", "RB", "PHI", fantasy_positions=["RB", "WR"]),
    "2004": _p("2004", "Injured", "Runner", "RB", "MIA", status="Injured Reserve", injury="IR", body="Knee"),
    "2005": _p("2005", "Opp", "RunnerOne", "RB", "DAL"),
    "2006": _p("2006", "Opp", "RunnerTwo", "RB", "NYG"),
    "3001": _p("3001", "Sky", "Hands", "WR", "CIN"),
    "3002": _p("3002", "Slot", "Machine", "WR", "MIN", injury="Questionable", body="Hamstring"),
    "3003": _p("3003", "Deep", "Threat", "WR", "LAR"),
    "3004": _p("3004", "Bench", "Receiver", "WR", "SEA"),
    "3005": _p("3005", "Opp", "WideOne", "WR", "HOU"),
    "3006": _p("3006", "Opp", "WideTwo", "WR", "TEN"),
    "4001": _p("4001", "Tall", "Target", "TE", "BAL"),
    "4002": _p("4002", "Opp", "TightEnd", "TE", "ATL"),
    "5001": _p("5001", "Boot", "Legg", "K", "KC"),
    "5002": _p("5002", "Opp", "Kicker", "K", "BUF"),
    "KC": {"player_id": "KC", "first_name": "Kansas City", "last_name": "Chiefs", "position": "DEF", "fantasy_positions": ["DEF"], "team": "KC", "status": "Active"},
    "BUF": {"player_id": "BUF", "first_name": "Buffalo", "last_name": "Bills", "position": "DEF", "fantasy_positions": ["DEF"], "team": "BUF", "status": "Active"},
    # Free agents
    "6001": _p("6001", "Free", "Agent", "RB", "GB"),
    "6002": _p("6002", "Waiver", "Wire", "WR", "NO"),
    "6003": _p("6003", "Spare", "Tight", "TE", "CHI"),
    # Retired / irrelevant (no team) should not be persisted unless referenced
    "7001": _p("7001", "Old", "Timer", "QB", None, status="Inactive"),
    "9999": _p("9999", "Dropped", "Guy", "WR", "LV"),
}


def install(router):
    router.get("/state/nfl").mock(return_value=Response(200, json=STATE))
    router.get(f"/user/{USER['username']}").mock(return_value=Response(200, json=USER))
    router.get(f"/user/{USER_ID}").mock(return_value=Response(200, json=USER))
    router.get("/user/nobody_here").mock(return_value=Response(200, json=None))
    router.get(f"/user/{USER_ID}/leagues/nfl/2026").mock(return_value=Response(200, json=LEAGUES))
    router.get(f"/league/{LEAGUE_ID}").mock(return_value=Response(200, json=LEAGUE))
    router.get(f"/league/{LEAGUE_ID}/rosters").mock(return_value=Response(200, json=ROSTERS))
    router.get(f"/league/{LEAGUE_ID}/users").mock(return_value=Response(200, json=USERS))
    router.get(f"/league/{LEAGUE_ID}/matchups/4").mock(return_value=Response(200, json=MATCHUPS_W4))
    router.get(f"/league/{LEAGUE_ID}/matchups/3").mock(return_value=Response(200, json=MATCHUPS_W3))
    router.get(f"/league/{LEAGUE_ID}/matchups/2").mock(return_value=Response(200, json=[]))
    router.get(f"/league/{LEAGUE_ID}/matchups/1").mock(return_value=Response(200, json=[]))
    router.get(f"/league/{LEAGUE_ID}/transactions/4").mock(return_value=Response(200, json=[]))
    router.get(f"/league/{LEAGUE_ID}/transactions/3").mock(return_value=Response(200, json=TRANSACTIONS_W3))
    router.get(f"/league/{LEAGUE_ID}/transactions/2").mock(return_value=Response(200, json=[]))
    router.get(f"/league/{LEAGUE_ID}/transactions/1").mock(return_value=Response(200, json=[]))
    router.get("/league/000").mock(return_value=Response(404))
    router.get("/players/nfl").mock(return_value=Response(200, json=PLAYERS))
