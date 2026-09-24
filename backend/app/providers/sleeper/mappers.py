"""Pure functions converting raw Sleeper JSON into normalized DTOs.

Kept side-effect free so they are trivially unit-testable.
"""

from datetime import UTC, datetime
from typing import Any

from app.domain.enums import NON_LINEUP_SLOTS
from app.domain.provider_models import (
    LeagueDetails,
    LeagueSummary,
    MatchupData,
    PlayerData,
    ProviderState,
    ProviderUser,
    RosterData,
    RosterSlotEntry,
    TeamData,
    TransactionData,
)

EMPTY_SLOT = "0"
SLEEPER_WAIVER_TYPES = {0: "rolling", 1: "reverse_standings", 2: "faab"}


def _avatar_url(avatar_id: str | None) -> str | None:
    return f"https://sleepercdn.com/avatars/thumbs/{avatar_id}" if avatar_id else None


def _scoring_type(scoring: dict[str, Any]) -> str:
    rec = float(scoring.get("rec", 0) or 0)
    if rec >= 1:
        return "PPR"
    if rec > 0:
        return "Half PPR"
    return "Standard"


def map_state(raw: dict[str, Any]) -> ProviderState:
    return ProviderState(
        season=int(raw.get("season") or raw.get("league_season") or 0),
        week=int(raw.get("week") or raw.get("display_week") or 1),
        season_type=str(raw.get("season_type") or "regular"),
    )


def map_user(raw: dict[str, Any]) -> ProviderUser:
    return ProviderUser(
        external_user_id=str(raw["user_id"]),
        username=str(raw.get("username") or raw.get("display_name") or raw["user_id"]),
        display_name=raw.get("display_name"),
        avatar=_avatar_url(raw.get("avatar")),
    )


def map_league_summary(raw: dict[str, Any]) -> LeagueSummary:
    return LeagueSummary(
        external_league_id=str(raw["league_id"]),
        name=str(raw.get("name") or "Unnamed league"),
        season=int(raw.get("season") or 0),
        team_count=int(raw.get("total_rosters") or (raw.get("settings") or {}).get("num_teams") or 0),
        status=raw.get("status"),
        avatar=_avatar_url(raw.get("avatar")),
        scoring_type=_scoring_type(raw.get("scoring_settings") or {}),
    )


def map_league_details(raw: dict[str, Any], fallback_week: int | None = None) -> LeagueDetails:
    settings = raw.get("settings") or {}
    week = settings.get("leg") or fallback_week or 1
    roster_positions = [str(p) for p in raw.get("roster_positions") or []]
    lineup = [p for p in roster_positions if p not in NON_LINEUP_SLOTS]
    return LeagueDetails(
        external_league_id=str(raw["league_id"]),
        name=str(raw.get("name") or "Unnamed league"),
        season=int(raw.get("season") or 0),
        team_count=int(raw.get("total_rosters") or settings.get("num_teams") or 0),
        current_week=int(week),
        status=raw.get("status"),
        avatar=_avatar_url(raw.get("avatar")),
        scoring_settings={k: float(v) for k, v in (raw.get("scoring_settings") or {}).items()},
        roster_positions=roster_positions,
        roster_settings={
            "roster_positions": roster_positions,
            "lineup_slots": lineup,
            "bench_slots": roster_positions.count("BN"),
            "reserve_slots": int(settings.get("reserve_slots") or 0),
            "taxi_slots": int(settings.get("taxi_slots") or 0),
            "max_roster_size": len(roster_positions),
        },
        league_settings={
            "scoring_type": _scoring_type(raw.get("scoring_settings") or {}),
            "waiver_type": SLEEPER_WAIVER_TYPES.get(settings.get("waiver_type"), "unknown"),
            "waiver_budget": settings.get("waiver_budget"),
            "waiver_day_of_week": settings.get("waiver_day_of_week"),
            "playoff_week_start": settings.get("playoff_week_start"),
            "playoff_teams": settings.get("playoff_teams"),
            "trade_deadline": settings.get("trade_deadline"),
            "best_ball": bool(settings.get("best_ball")),
            "league_type": settings.get("type"),  # 0 redraft, 1 keeper, 2 dynasty
            "draft_id": raw.get("draft_id"),
            "previous_league_id": raw.get("previous_league_id"),
        },
    )


def _points(settings: dict[str, Any], key: str) -> float:
    whole = settings.get(key) or 0
    decimal = settings.get(f"{key}_decimal") or 0
    return float(whole) + float(decimal) / 100.0


def map_teams(
    rosters: list[dict[str, Any]],
    users: list[dict[str, Any]],
    waiver_budget: int | None,
) -> list[TeamData]:
    users_by_id = {str(u["user_id"]): u for u in users if u.get("user_id")}
    teams: list[TeamData] = []
    for roster in rosters:
        settings = roster.get("settings") or {}
        owner_id = str(roster["owner_id"]) if roster.get("owner_id") else None
        user = users_by_id.get(owner_id or "", {})
        meta = user.get("metadata") or {}
        name = meta.get("team_name") or user.get("display_name") or f"Team {roster['roster_id']}"
        faab = None
        if waiver_budget is not None:
            faab = int(waiver_budget) - int(settings.get("waiver_budget_used") or 0)
        teams.append(
            TeamData(
                external_team_id=str(roster["roster_id"]),
                owner_external_id=owner_id,
                owner_name=user.get("display_name"),
                name=str(name),
                avatar=_avatar_url(meta.get("avatar") or user.get("avatar")),
                wins=int(settings.get("wins") or 0),
                losses=int(settings.get("losses") or 0),
                ties=int(settings.get("ties") or 0),
                points_for=round(_points(settings, "fpts"), 2),
                points_against=round(_points(settings, "fpts_against"), 2),
                faab_remaining=faab,
                waiver_position=settings.get("waiver_position"),
                settings={
                    "total_moves": settings.get("total_moves"),
                    "co_owners": roster.get("co_owners") or [],
                },
            )
        )
    return teams


def map_roster(raw: dict[str, Any], roster_positions: list[str]) -> RosterData:
    """Align Sleeper's ordered `starters` list with the league's roster_positions."""
    lineup_slots = [p for p in roster_positions if p not in NON_LINEUP_SLOTS]
    starters = [str(p) for p in raw.get("starters") or []]
    reserve = {str(p) for p in raw.get("reserve") or []}
    taxi = {str(p) for p in raw.get("taxi") or []}
    all_players = [str(p) for p in raw.get("players") or []]

    entries: list[RosterSlotEntry] = []
    seen: set[str] = set()
    for idx, pid in enumerate(starters):
        if pid == EMPTY_SLOT or not pid:
            continue
        slot = lineup_slots[idx] if idx < len(lineup_slots) else "FLEX"
        entries.append(RosterSlotEntry(external_player_id=pid, roster_slot=slot, is_starter=True, slot_index=idx))
        seen.add(pid)
    for pid in all_players:
        if pid in seen:
            continue
        slot = "IR" if pid in reserve else "TAXI" if pid in taxi else "BN"
        entries.append(RosterSlotEntry(external_player_id=pid, roster_slot=slot, is_starter=False))
        seen.add(pid)
    return RosterData(external_team_id=str(raw["roster_id"]), entries=entries)


def map_matchup(raw: dict[str, Any], week: int) -> MatchupData:
    return MatchupData(
        external_matchup_id=str(raw["matchup_id"]) if raw.get("matchup_id") is not None else None,
        week=week,
        external_team_id=str(raw["roster_id"]),
        points=float(raw.get("points") or 0.0),
        projected_points=None,  # not provided by the public Sleeper API
        player_points={str(k): float(v) for k, v in (raw.get("players_points") or {}).items()},
    )


def map_transaction(raw: dict[str, Any]) -> TransactionData:
    created_ms = raw.get("status_updated") or raw.get("created") or 0
    created = datetime.fromtimestamp(int(created_ms) / 1000, tz=UTC)
    adds = [
        {"external_player_id": str(pid), "external_team_id": str(rid)}
        for pid, rid in (raw.get("adds") or {}).items()
    ]
    drops = [
        {"external_player_id": str(pid), "external_team_id": str(rid)}
        for pid, rid in (raw.get("drops") or {}).items()
    ]
    settings = raw.get("settings") or {}
    return TransactionData(
        external_transaction_id=str(raw["transaction_id"]),
        type=str(raw.get("type") or "unknown"),
        status=str(raw.get("status") or "unknown"),
        week=int(raw["leg"]) if raw.get("leg") is not None else None,
        created_at=created,
        adds=adds,
        drops=drops,
        external_team_ids=[str(r) for r in raw.get("roster_ids") or []],
        faab_bid=settings.get("waiver_bid"),
        metadata={
            "draft_picks": raw.get("draft_picks") or [],
            "waiver_budget": raw.get("waiver_budget") or [],
            "notes": (raw.get("metadata") or {}).get("notes"),
            "creator": raw.get("creator"),
        },
    )


def map_player(player_id: str, raw: dict[str, Any]) -> PlayerData:
    first = raw.get("first_name")
    last = raw.get("last_name")
    name = raw.get("full_name") or " ".join(p for p in (first, last) if p) or player_id
    return PlayerData(
        external_player_id=str(player_id),
        name=str(name),
        first_name=first,
        last_name=last,
        position=raw.get("position"),
        fantasy_positions=[str(p) for p in raw.get("fantasy_positions") or [] if p],
        nfl_team=raw.get("team"),
        status=raw.get("status"),
        injury_status=raw.get("injury_status") or None,
        injury_body_part=raw.get("injury_body_part") or None,
        age=raw.get("age"),
        years_exp=raw.get("years_exp"),
        number=raw.get("number"),
        extra={
            "depth_chart_order": raw.get("depth_chart_order"),
            "depth_chart_position": raw.get("depth_chart_position"),
            "practice_participation": raw.get("practice_participation"),
            "injury_notes": raw.get("injury_notes"),
            "espn_id": str(raw["espn_id"]) if raw.get("espn_id") else None,
        },
    )
