"""Fake 12-team PPR league for demo mode.

Produces an ImportedLeagueSnapshot (the same shape a real provider returns)
so it flows through SyncService exactly like a Sleeper import, plus NFL data
(bye weeks, projections, stats) for the LocalFileNFLDataProvider.

All players are fictional.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.domain.enums import Provider
from app.domain.provider_models import (
    ImportedLeagueSnapshot,
    LeagueDetails,
    MatchupData,
    PlayerData,
    ProviderUser,
    RosterData,
    RosterSlotEntry,
    TeamData,
    TransactionData,
)
from app.nfl_data.base import player_key

DEMO_USER = ProviderUser(external_user_id="demo-user", username="demo_manager", display_name="Demo Manager")
DEMO_LEAGUE_ID = "demo-league-2026"
SEASON = 2026
CURRENT_WEEK = 4

ROSTER_POSITIONS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN", "BN", "BN", "BN", "IR"]
LINEUP = [p for p in ROSTER_POSITIONS if p not in ("BN", "IR")]

NFL_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS",
]
BYE_WEEKS = {t: 5 + (i % 10) for i, t in enumerate(NFL_TEAMS)}  # byes weeks 5-14 (+ one week-4 bye set below)

FIRST = ["Marcus", "Devon", "Tyler", "Jalen", "Cade", "Isaiah", "Brock", "Xavier", "Kellen", "Dante", "Reese", "Jordan",
         "Malik", "Trey", "Cameron", "Elijah", "Nico", "Rashad", "Zane", "Quincy", "Tariq", "Emeka", "Bryce", "Kai"]
LAST = ["Whitfield", "Okafor", "Brandt", "Castellano", "Pruitt", "Delgado", "Hargrove", "Lindqvist", "Marlowe", "Nakamura",
        "Osei", "Prescott", "Quintero", "Rowe", "Sandoval", "Thibodeaux", "Vance", "Winslow", "Yates", "Zimmer",
        "Abernathy", "Beaumont", "Carrick", "Dumont"]

TEAM_NAMES = [
    "Gridiron Gurus", "Touchdown Titans", "Waiver Wire Wizards", "Blitz Brigade", "End Zone Elite", "Pigskin Prophets",
    "Fourth and Long", "Red Zone Raiders", "Hail Mary Heroes", "Sunday Scaries", "The Replacements", "Bench Warmers",
]
OWNERS = ["Demo Manager", "Alex Rivera", "Sam Chen", "Jordan Blake", "Priya Nair", "Chris Doyle", "Taylor Kim",
          "Morgan Lee", "Dana Ortiz", "Casey Hughes", "Riley Fox", "Jamie Patel"]

# Per position: (count in pool, projection mean by tier)
POOL = {"QB": 26, "RB": 60, "WR": 72, "TE": 28, "K": 20, "DEF": 32}
TIER_PROJ = {"QB": (24, 12), "RB": (20, 5), "WR": (19, 5), "TE": (14, 4), "K": (10, 6), "DEF": (9, 5)}


def _rng() -> random.Random:
    return random.Random(2026)


def build_players(rng: random.Random) -> dict[str, PlayerData]:
    players: dict[str, PlayerData] = {}
    used_names: set[str] = set()
    idx = 1
    for pos, count in POOL.items():
        for rank in range(count):
            if pos == "DEF":
                team = NFL_TEAMS[rank]
                pid = f"demo-DEF-{team}"
                players[pid] = PlayerData(
                    external_player_id=pid, name=f"{team} Defense", first_name=team, last_name="Defense",
                    position="DEF", fantasy_positions=["DEF"], nfl_team=team, status="Active",
                )
                continue
            while True:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if name not in used_names:
                    used_names.add(name)
                    break
            first, last = name.split(" ", 1)
            pid = f"demo-{idx:04d}"
            idx += 1
            players[pid] = PlayerData(
                external_player_id=pid, name=name, first_name=first, last_name=last, position=pos,
                fantasy_positions=[pos] if pos != "RB" or rank % 9 else ["RB", "WR"],
                nfl_team=NFL_TEAMS[(rank * 7 + idx) % len(NFL_TEAMS)], status="Active",
                age=rng.randint(22, 33), years_exp=rng.randint(0, 11), number=rng.randint(1, 99),
                extra={"demo_rank": rank},
            )
    return players


def build_snapshot() -> tuple[ImportedLeagueSnapshot, dict]:
    rng = _rng()
    players = build_players(rng)
    by_pos: dict[str, list[PlayerData]] = {pos: [] for pos in POOL}
    for p in players.values():
        by_pos[p.position].append(p)  # type: ignore[index]
    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: p.extra.get("demo_rank", 0) if p.position != "DEF" else NFL_TEAMS.index(p.nfl_team or "ARI"))

    # Snake-ish distribution: team i gets rank-ordered players so rosters are balanced.
    def draft(pos: str, per_team: int) -> list[list[PlayerData]]:
        pool = by_pos[pos]
        out: list[list[PlayerData]] = [[] for _ in range(12)]
        order = list(range(12))
        i = 0
        for _round in range(per_team):
            for t in order:
                if i < len(pool):
                    out[t].append(pool[i])
                    i += 1
            order.reverse()
        return out

    qbs, rbs, wrs, tes, ks, defs = draft("QB", 1), draft("RB", 4), draft("WR", 5), draft("TE", 2), draft("K", 1), draft("DEF", 1)

    rosters: list[RosterData] = []
    teams: list[TeamData] = []
    projections: dict[str, dict] = {}
    season_stats: dict[str, dict] = {}
    news: dict[str, list[dict]] = {}

    for t in range(12):
        roster_players = qbs[t] + rbs[t] + wrs[t] + tes[t] + ks[t] + defs[t]  # 14 players
        # starters
        starters = [qbs[t][0], rbs[t][0], rbs[t][1], wrs[t][0], wrs[t][1], tes[t][0], wrs[t][2], ks[t][0], defs[t][0]]
        entries = [RosterSlotEntry(external_player_id=p.external_player_id, roster_slot=LINEUP[i], is_starter=True, slot_index=i) for i, p in enumerate(starters)]
        bench = [p for p in roster_players if p not in starters]
        for p in bench:
            entries.append(RosterSlotEntry(external_player_id=p.external_player_id, roster_slot="BN", is_starter=False))
        rosters.append(RosterData(external_team_id=str(t + 1), entries=entries))

    # Storylines for the user's team (team 1): WR2 questionable, TE on bye, bench RB out, a WR on IR.
    user_wr2 = wrs[0][1]
    user_wr2.injury_status = "Questionable"
    user_wr2.injury_body_part = "Hamstring"
    user_te = tes[0][0]
    # Give the starting TE's NFL team a Week 4 bye (every other team's bye is week 5+).
    BYE_WEEKS[user_te.nfl_team or "ARI"] = CURRENT_WEEK
    bench_rb = rbs[0][3]
    bench_rb.injury_status = "Out"
    bench_rb.injury_body_part = "Ankle"
    ir_wr = wrs[0][4]
    ir_wr.injury_status = "IR"
    ir_wr.injury_body_part = "Knee"
    for e in rosters[0].entries:
        if e.external_player_id == ir_wr.external_player_id:
            e.roster_slot = "IR"
    # Sprinkle injuries elsewhere
    for t in range(1, 12):
        if t % 3 == 0:
            p = rbs[t][1]
            p.injury_status, p.injury_body_part = "Questionable", "Shoulder"
        if t % 4 == 0:
            p = wrs[t][0]
            p.injury_status, p.injury_body_part = "Out", "Concussion"

    # Projections & season stats for every player (fictional but internally consistent)
    for pos, pool in by_pos.items():
        mean, spread = TIER_PROJ[pos]
        for i, p in enumerate(pool):
            tier_factor = max(0.25, 1 - i / max(len(pool), 1) * 0.9)
            base = mean * tier_factor
            key = player_key(p.name, p.position, p.nfl_team)
            proj = round(max(0.0, rng.gauss(base, spread * 0.15)), 1)
            if p.injury_status in ("Out", "IR"):
                proj = 0.0
            if BYE_WEEKS.get(p.nfl_team or "", 0) == CURRENT_WEEK:
                proj = 0.0
            projections[key] = {"points": proj, "source": "demo"}
            games = 3
            total = round(sum(max(0.0, rng.gauss(base, spread * 0.4)) for _ in range(games)), 1)
            season_stats[key] = {"games_played": games, "fantasy_points": total, "source": "demo"}
    news[player_key(user_wr2.name, "WR", user_wr2.nfl_team)] = [
        {"headline": f"{user_wr2.name} limited in practice with hamstring tightness", "published_at": "2026-09-23", "source": "demo"}
    ]
    news[player_key(bench_rb.name, "RB", bench_rb.nfl_team)] = [
        {"headline": f"{bench_rb.name} ruled out for Week {CURRENT_WEEK} (ankle)", "published_at": "2026-09-22", "source": "demo"}
    ]

    # Matchups weeks 1-4
    matchups: list[MatchupData] = []
    records = {t: [0, 0] for t in range(1, 13)}
    pf = {t: 0.0 for t in range(1, 13)}
    pa = {t: 0.0 for t in range(1, 13)}
    for week in range(1, CURRENT_WEEK + 1):
        order = list(range(1, 13))
        rng.shuffle(order)
        for m in range(6):
            a, b = order[2 * m], order[2 * m + 1]
            if week < CURRENT_WEEK:
                pa_, pb_ = round(rng.uniform(85, 145), 2), round(rng.uniform(85, 145), 2)
                records[a if pa_ > pb_ else b][0] += 1
                records[b if pa_ > pb_ else a][1] += 1
                pf[a] += pa_
                pf[b] += pb_
                pa[a] += pb_
                pa[b] += pa_
            else:
                pa_ = pb_ = 0.0
            for team_id, pts in ((a, pa_), (b, pb_)):
                roster = rosters[team_id - 1]
                starter_ids = [e.external_player_id for e in roster.entries if e.is_starter]
                pp = {}
                if pts:
                    weights = [rng.uniform(0.5, 1.5) for _ in starter_ids]
                    total_w = sum(weights)
                    pp = {pid: round(pts * w / total_w, 2) for pid, w in zip(starter_ids, weights, strict=True)}
                matchups.append(MatchupData(external_matchup_id=str(m + 1), week=week, external_team_id=str(team_id), points=pts, player_points=pp))

    budget = 100
    for t in range(12):
        tid = t + 1
        teams.append(
            TeamData(
                external_team_id=str(tid),
                owner_external_id=DEMO_USER.external_user_id if tid == 1 else f"demo-owner-{tid}",
                owner_name=OWNERS[t],
                name=TEAM_NAMES[t],
                wins=records[tid][0], losses=records[tid][1], ties=0,
                points_for=round(pf[tid], 2), points_against=round(pa[tid], 2),
                faab_remaining=budget - (0 if tid != 1 else 18) - (rng.randint(0, 40) if tid != 1 else 0),
                waiver_position=((tid * 5) % 12) + 1,
            )
        )

    # Transactions: a few waivers + one trade in recent weeks
    now = datetime.now(UTC)
    free_agents = [p for p in players.values() if not any(p.external_player_id == e.external_player_id for r in rosters for e in r.entries)]
    txs: list[TransactionData] = []
    for i in range(6):
        team = rng.randint(2, 12)
        add = rng.choice([p for p in free_agents if p.position in ("RB", "WR", "TE")])
        drop = rng.choice([e for e in rosters[team - 1].entries if not e.is_starter and e.roster_slot == "BN"])
        txs.append(
            TransactionData(
                external_transaction_id=f"demo-tx-{i + 1}", type="waiver", status="complete", week=CURRENT_WEEK - (i % 3),
                created_at=now - timedelta(days=i + 1),
                adds=[{"external_player_id": add.external_player_id, "external_team_id": str(team)}],
                drops=[{"external_player_id": drop.external_player_id, "external_team_id": str(team)}],
                external_team_ids=[str(team)], faab_bid=rng.choice([3, 7, 12, 21]),
            )
        )
    # user's own waiver add last week
    txs.append(
        TransactionData(
            external_transaction_id="demo-tx-user", type="waiver", status="complete", week=CURRENT_WEEK - 1,
            created_at=now - timedelta(days=2),
            adds=[{"external_player_id": rbs[0][2].external_player_id, "external_team_id": "1"}],
            drops=[{"external_player_id": free_agents[0].external_player_id, "external_team_id": "1"}],
            external_team_ids=["1"], faab_bid=18,
        )
    )
    txs.append(
        TransactionData(
            external_transaction_id="demo-tx-trade", type="trade", status="complete", week=CURRENT_WEEK - 1,
            created_at=now - timedelta(days=4),
            adds=[
                {"external_player_id": wrs[2][1].external_player_id, "external_team_id": "4"},
                {"external_player_id": rbs[3][1].external_player_id, "external_team_id": "3"},
            ],
            external_team_ids=["3", "4"],
        )
    )

    league = LeagueDetails(
        external_league_id=DEMO_LEAGUE_ID,
        name="Demo Dynasty Invitational (PPR)",
        season=SEASON,
        team_count=12,
        current_week=CURRENT_WEEK,
        status="in_season",
        scoring_settings={"pass_yd": 0.04, "pass_td": 4.0, "pass_int": -2.0, "rush_yd": 0.1, "rush_td": 6.0, "rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "fum_lost": -2.0, "fgm": 3.0, "xpm": 1.0, "def_td": 6.0, "sack": 1.0, "int": 2.0},
        roster_positions=ROSTER_POSITIONS,
        roster_settings={"roster_positions": ROSTER_POSITIONS, "lineup_slots": LINEUP, "bench_slots": 6, "reserve_slots": 1, "taxi_slots": 0, "max_roster_size": len(ROSTER_POSITIONS)},
        league_settings={"scoring_type": "PPR", "waiver_type": "faab", "waiver_budget": budget, "playoff_week_start": 15, "playoff_teams": 6, "trade_deadline": 12, "league_type": 0},
    )

    schedule = {str(w): {} for w in range(1, 19)}
    for w in range(1, 19):
        active = [t for t in NFL_TEAMS if BYE_WEEKS[t] != w]
        rng.shuffle(active)
        for i in range(0, len(active) - 1, 2):
            schedule[str(w)][active[i]] = active[i + 1]
            schedule[str(w)][active[i + 1]] = active[i]

    nfl_data = {
        "bye_weeks": {str(SEASON): BYE_WEEKS},
        "schedule": {str(SEASON): schedule},
        "projections": {str(SEASON): {str(CURRENT_WEEK): projections}},
        "season_stats": {str(SEASON): season_stats},
        "news": news,
    }
    snapshot = ImportedLeagueSnapshot(
        provider=Provider.DEMO, league=league, teams=teams, rosters=rosters, matchups=matchups, transactions=txs, players=players
    )
    return snapshot, nfl_data
