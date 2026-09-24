"""Concrete AI tools. Each returns compact, provider-neutral JSON.

Tools deliberately return summaries (not whole tables) to keep prompts small.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.tools.base import EmptyArgs, ToolContext, ToolRegistry
from app.core.errors import NotFoundError
from app.intelligence.lineup import eligible_positions_for_slot, is_eligible
from app.intelligence.recommendations import generate_recommendations
from app.nfl_data.props import norm_name
from app.schemas.league import LineupUpdateRequest, PlayerOut, RosterMoveRequest, RosterSlotOut

registry = ToolRegistry()


def _player_brief(p: PlayerOut) -> dict[str, Any]:
    return {
        "player_id": str(p.id),
        "name": p.name,
        "position": p.position,
        "nfl_team": p.nfl_team,
        "injury_status": p.injury_status,
        "injury_body_part": p.injury_body_part,
        "bye_week": p.bye_week,
        "on_bye_this_week": p.on_bye,
        "opponent_this_week": p.opponent,
        "projected_points": p.projected_points,
        "projection_note": p.projection_note,
        "season_points": p.season_points,
        "points_per_game": p.points_per_game,
        "season_schedule": [
            f"W{g.week} BYE"
            if not g.opponent
            else f"W{g.week} {'@' if g.home is False else 'vs'} {g.opponent}"
            for g in p.schedule
        ],
    }


def _slot_brief(s: RosterSlotOut) -> dict[str, Any]:
    d = _player_brief(s.player) if s.player else {"player_id": None, "name": "EMPTY"}
    d.update({"slot": s.slot, "is_starter": s.is_starter, "flags": s.flags, "points_this_week": s.points})
    return d


# ---- Args --------------------------------------------------------------------


class PlayerIdArgs(BaseModel):
    player_id: str = Field(description="Internal player id (UUID) from a previous tool result")


class AvailablePlayersArgs(BaseModel):
    position: str | None = Field(default=None, description="QB, RB, WR, TE, K or DEF. Omit for all.")
    limit: int = Field(default=10, ge=1, le=25)


class ComparePlayersArgs(BaseModel):
    player_ids: list[str] = Field(min_length=2, max_length=6, description="Internal player ids to compare")


class SlotArgs(BaseModel):
    slot: str = Field(description="Roster slot such as FLEX, RB, WR, SUPER_FLEX")


class ChangeLineupArgs(BaseModel):
    player_name: str = Field(description="A player already on the user's roster, matched by name.")
    destination: Literal["starter", "bench", "ir"] = Field(
        description="starter puts them in the scoring lineup, bench takes them out, ir moves them to injured reserve."
    )
    slot: str | None = Field(
        default=None,
        description="Starting slot when destination is starter, such as FLEX or RB2. Omit to use the first open eligible slot.",
    )


class SetLineupArgs(BaseModel):
    starters: list[str | None] = Field(
        min_length=1,
        max_length=20,
        description="One roster player name per starting slot, in lineup_slots order from get_roster. Use null for an empty slot.",
    )


class SearchPlayersArgs(BaseModel):
    query: str = Field(min_length=2, max_length=60, description="Part of a player name")
    limit: int = Field(default=5, ge=1, le=10)


# ---- Tools -------------------------------------------------------------------


@registry.tool(
    "get_team",
    "The user's team: name, record, points, FAAB, waiver position, standings rank and this week's matchup opponent.",
)
async def get_team(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    rank = next((row.rank for row in tc.standings if row.is_user_team), None)
    return {
        "league": tc.league_name,
        "season": tc.season,
        "week": tc.week,
        "scoring_type": tc.scoring_type,
        "team": tc.team.team.model_dump(mode="json"),
        "standings_rank": rank,
        "league_size": len(tc.standings),
        "projected_points": tc.team.projected_points,
        "projection_coverage": tc.team.projection_coverage,
        "opponent": tc.matchup.opponent.team.name if tc.matchup and tc.matchup.opponent else None,
    }


@registry.tool(
    "get_roster",
    "Full roster for the user's team: starters by slot, bench and IR, with injury flags, bye weeks and projections when available.",
)
async def get_roster(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    return {
        "week": tc.week,
        "lineup_slots": tc.lineup_slots,
        "starters": [_slot_brief(s) for s in tc.team.starters],
        "bench": [_slot_brief(s) for s in tc.team.bench],
        "reserve": [_slot_brief(s) for s in tc.team.reserve],
        "lineup_issues": tc.team.lineup_issues,
        "projections_available": tc.projections_available,
        "bye_weeks_available": tc.bye_weeks_available,
    }


@registry.tool(
    "get_league_settings",
    "Scoring rules (e.g. PPR, TD values), roster slots, waiver type/FAAB budget and playoff settings.",
)
async def get_league_settings(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    lg = ctx.league
    key_scoring = {
        k: v
        for k, v in lg.scoring_settings.items()
        if k in {"rec", "pass_td", "rush_td", "rec_td", "pass_yd", "rush_yd", "rec_yd", "pass_int", "fum_lost", "bonus_rec_te", "rec_bonus"}
    }
    return {
        "name": lg.name,
        "season": lg.season,
        "current_week": lg.current_week,
        "team_count": lg.team_count,
        "scoring_type": lg.league_settings.get("scoring_type"),
        "key_scoring": key_scoring,
        "roster_positions": lg.roster_positions,
        "roster_settings": lg.roster_settings,
        "waiver_type": lg.league_settings.get("waiver_type"),
        "waiver_budget": lg.league_settings.get("waiver_budget"),
        "playoff_week_start": lg.league_settings.get("playoff_week_start"),
        "playoff_teams": lg.league_settings.get("playoff_teams"),
        "trade_deadline_week": lg.league_settings.get("trade_deadline"),
    }


@registry.tool(
    "get_current_matchup",
    "This week's matchup: both starting lineups, actual points so far and projected totals when available.",
)
async def get_current_matchup(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    if tc.matchup is None:
        return {"week": tc.week, "matchup": None, "note": "No matchup data stored for this week."}
    m = tc.matchup
    return {
        "week": m.week,
        "status": m.status,
        "is_bye": m.is_bye,
        "user": {
            "team": m.user.team.name,
            "points": m.user.points,
            "projected_points": m.user.projected_points,
            "starters": [_slot_brief(s) for s in m.user.starters],
        },
        "opponent": None
        if m.opponent is None
        else {
            "team": m.opponent.team.name,
            "record": m.opponent.team.record,
            "points": m.opponent.points,
            "projected_points": m.opponent.projected_points,
            "starters": [_slot_brief(s) for s in m.opponent.starters],
        },
    }


@registry.tool("get_player", "Details for one player in this league's player pool, by internal id.", PlayerIdArgs)
async def get_player(ctx: ToolContext, args: PlayerIdArgs) -> dict[str, Any]:
    p = await ctx.service.get_player_in_league(ctx.league, _uuid(args.player_id), ctx.week)
    tc = await ctx.team_context()
    on_roster = any(s.player and s.player.id == p.id for s in tc.all_roster)
    return {**_player_brief(p), "status": p.status, "age": p.age, "years_exp": p.years_exp, "on_user_roster": on_roster}


@registry.tool(
    "get_player_stats",
    "Season stats, this-week projection and recent news for a player, when the data provider has them. Returns nulls when unavailable - never guess.",
    PlayerIdArgs,
)
async def get_player_stats(ctx: ToolContext, args: PlayerIdArgs) -> dict[str, Any]:
    from app.nfl_data import player_key

    p = await ctx.service.get_player_in_league(ctx.league, _uuid(args.player_id), ctx.week)
    key = player_key(p.name, p.position, p.nfl_team)
    stats = await ctx.service.nfl_data.get_season_stats(key, ctx.league.season)
    proj = await ctx.service.nfl_data.get_projection(key, ctx.league.season, ctx.week)
    news = await ctx.service.nfl_data.get_news(key)
    projection = proj.model_dump() if proj else None
    if projection is None and p.projected_points is not None:
        projection = {
            "week": ctx.week,
            "points": p.projected_points,
            "source": "vegas",
            "detail": {},
            "note": p.projection_note,
        }
    return {
        "player": _player_brief(p),
        "season_stats": stats.model_dump() if stats else None,
        "projection": projection,
        "news": [n.model_dump() for n in news],
        "data_source": ctx.service.nfl_data.name,
        "note": None
        if (stats or projection)
        else "No stats or projections are available for this player from the configured data source.",
    }


@registry.tool(
    "get_available_players",
    "Best available free agents / waiver players in this league, optionally filtered by position. Sorted by projection when available.",
    AvailablePlayersArgs,
)
async def get_available_players(ctx: ToolContext, args: AvailablePlayersArgs) -> dict[str, Any]:
    players = await ctx.service.available_players(
        ctx.league, position=args.position, limit=args.limit, week=ctx.week
    )
    return {
        "position": args.position,
        "waiver_type": ctx.league.league_settings.get("waiver_type"),
        "players": [_player_brief(p) for p in players],
        "projections_available": any(p.projected_points is not None for p in players),
    }


@registry.tool("search_players", "Find a player in this league's pool by (partial) name.", SearchPlayersArgs)
async def search_players(ctx: ToolContext, args: SearchPlayersArgs) -> dict[str, Any]:
    players = await ctx.service.search_players(ctx.league, search=args.query, position=None, limit=args.limit, week=ctx.week)
    tc = await ctx.team_context()
    roster_ids = {s.player.id for s in tc.all_roster if s.player}
    rostered_league = await ctx.service.players.rostered_player_ids(ctx.league.id, ctx.week)
    return {
        "results": [
            {
                **_player_brief(p),
                "on_user_roster": p.id in roster_ids,
                "rostered_in_league": p.id in rostered_league,
            }
            for p in players
        ]
    }


@registry.tool("get_recent_transactions", "Recent waivers, free-agent moves and trades in the league.")
async def get_recent_transactions(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    return {
        "transactions": [
            {
                "type": t.type,
                "status": t.status,
                "week": t.week,
                "date": t.created_at.isoformat(),
                "teams": t.team_names,
                "adds": [f"{a.get('player_name')} ({a.get('position')}) -> {a.get('team_name')}" for a in t.adds],
                "drops": [f"{d.get('player_name')} ({d.get('position')}) <- {d.get('team_name')}" for d in t.drops],
                "faab_bid": t.faab_bid,
                "involves_user": t.involves_user,
            }
            for t in tc.recent_transactions
        ]
    }


@registry.tool("compare_players", "Side-by-side facts for 2-6 players (position, injury, bye, projection, stats).", ComparePlayersArgs)
async def compare_players(ctx: ToolContext, args: ComparePlayersArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    roster_ids = {s.player.id for s in tc.all_roster if s.player}
    out = []
    for pid in args.player_ids:
        p = await ctx.service.get_player_in_league(ctx.league, _uuid(pid), ctx.week)
        out.append({**_player_brief(p), "on_user_roster": p.id in roster_ids})
    have_proj = [p for p in out if p["projected_points"] is not None]
    leader = max(have_proj, key=lambda p: p["projected_points"])["name"] if len(have_proj) == len(out) and out else None
    return {"players": out, "projection_leader": leader, "all_projections_available": leader is not None}


@registry.tool(
    "get_roster_needs",
    "Deterministic positional grades (Strong/Adequate/Needs depth/Weak), weakest and surplus positions, open roster spots.",
)
async def get_roster_needs(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    return tc.needs.model_dump(mode="json")


@registry.tool("get_standings", "League standings with records and points.")
async def get_standings(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    return {
        "standings": [
            {"rank": r.rank, "team": r.name, "record": r.record, "points_for": r.points_for, "is_user": r.is_user_team}
            for r in tc.standings
        ]
    }


@registry.tool(
    "get_recommendations",
    "Rule-based recommendations computed from the data (injuries, byes, start/sit swaps, waiver targets, weaknesses). Use these as grounded facts.",
)
async def get_recommendations(ctx: ToolContext, _: EmptyArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    recs = generate_recommendations(tc)
    return {"recommendations": [r.model_dump(mode="json") for r in recs]}


@registry.tool(
    "get_slot_options",
    "Every rostered player eligible for a given slot (e.g. FLEX) with availability flags and projections - use for start/sit questions.",
    SlotArgs,
)
async def get_slot_options(ctx: ToolContext, args: SlotArgs) -> dict[str, Any]:
    tc = await ctx.team_context()
    slot = args.slot.upper()
    eligible = [s for s in tc.team.starters + tc.team.bench if s.player and is_eligible(s.player, slot)]
    return {
        "slot": slot,
        "eligible_positions": list(eligible_positions_for_slot(slot)),
        "current_starter": next((_slot_brief(s) for s in tc.team.starters if s.slot == slot), None),
        "options": [_slot_brief(s) for s in eligible],
    }


_SLOT_ALIASES = {"DST": "DEF", "D": "DEF", "PK": "K", "DEFENSE": "DEF", "KICKER": "K"}


def _slot_key(label: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", label.upper())


def slot_index(slots: list[str], label: str) -> tuple[int | None, str | None]:
    text = _slot_key(label)
    match = re.fullmatch(r"([A-Z]+)(\d+)?", text)
    if not match:
        return None, f"Unknown slot {label}. Starting slots are {', '.join(slots)}."
    name = _SLOT_ALIASES.get(match.group(1), match.group(1))
    indexes = [i for i, slot in enumerate(slots) if _slot_key(slot) == name]
    if not indexes:
        return None, f"{label} is not a starting slot. Starting slots are {', '.join(slots)}."
    number = match.group(2)
    if number is None:
        if len(indexes) == 1:
            return indexes[0], None
        choices = ", ".join(f"{name}{i + 1}" for i in range(len(indexes)))
        return None, f"{name} has more than one slot. Say which one: {choices}."
    n = int(number)
    if n < 1 or n > len(indexes):
        return None, f"There is no {name}{n}."
    return indexes[n - 1], None


def find_roster_player(rows: list[RosterSlotOut], query: str) -> tuple[RosterSlotOut | None, str | None]:
    needle = norm_name(query)
    owned = [row for row in rows if row.player]
    if not needle:
        return None, "Name a player on the roster."
    exact = [row for row in owned if norm_name(row.player.name) == needle]
    hits = exact or [row for row in owned if needle in norm_name(row.player.name)]
    if not hits:
        return None, f"No rostered player matches {query}."
    if len(hits) > 1:
        names = ", ".join(row.player.name for row in hits if row.player)
        return None, f"More than one player matches {query}: {names}."
    return hits[0], None


def _lineup_result(result) -> dict[str, Any]:
    return {
        "verified": result.verified,
        "public_api_confirmed": result.public_api_confirmed,
        "message": result.message,
        "starters": [
            {"slot": row.slot, "player": row.player.name if row.player else None} for row in result.team.starters
        ],
    }


def _writes_missing() -> dict[str, str]:
    return {"error": "Lineup changes are unavailable in this session."}


def _current_week(ctx: ToolContext) -> None:
    if ctx.week != ctx.league.current_week:
        ctx.week = ctx.league.current_week
        ctx.invalidate()


@registry.tool(
    "change_lineup",
    "Move one rostered player to a starting slot, the bench, or IR for the current week. "
    "Writes the Sleeper scoring lineup and confirms it. Call only when the user asked to change the lineup. "
    "Demo leagues are read-only. Taxi moves are not supported.",
    ChangeLineupArgs,
)
async def change_lineup(ctx: ToolContext, args: ChangeLineupArgs) -> dict[str, Any]:
    if ctx.writes is None:
        return _writes_missing()
    _current_week(ctx)
    tc = await ctx.team_context()
    row, error = find_roster_player(tc.all_roster, args.player_name)
    if error or row is None or row.player is None:
        return {"error": error or "No rostered player matches that name."}
    slot_index_value = None
    if args.destination == "starter" and args.slot:
        slot_index_value, slot_error = slot_index(tc.lineup_slots, args.slot)
        if slot_error:
            return {"error": slot_error}
    body = RosterMoveRequest(
        week=ctx.league.current_week,
        player_id=row.player.id,
        destination=args.destination,
        slot_index=slot_index_value,
    )
    result = await ctx.writes.move_player(ctx.league, body)
    ctx.invalidate()
    return _lineup_result(result)


@registry.tool(
    "set_lineup",
    "Replace the entire current-week starting lineup. Pass one roster player name per slot, in lineup_slots order. "
    "Writes the Sleeper scoring lineup and confirms it. Call only when the user asked to set the lineup. "
    "Demo leagues are read-only.",
    SetLineupArgs,
)
async def set_lineup(ctx: ToolContext, args: SetLineupArgs) -> dict[str, Any]:
    if ctx.writes is None:
        return _writes_missing()
    _current_week(ctx)
    tc = await ctx.team_context()
    slots = tc.lineup_slots
    if len(args.starters) != len(slots):
        return {"error": f"Send one name per starting slot, in this order: {', '.join(slots)}."}
    ids: list[UUID | None] = []
    for name in args.starters:
        if name is None or not str(name).strip() or str(name).strip().lower() in {"0", "empty", "none"}:
            ids.append(None)
            continue
        row, error = find_roster_player(tc.all_roster, name)
        if error or row is None or row.player is None:
            return {"error": error or f"No rostered player matches {name}."}
        ids.append(row.player.id)
    result = await ctx.writes.set_lineup(ctx.league, LineupUpdateRequest(week=ctx.league.current_week, starter_player_ids=ids))
    ctx.invalidate()
    return _lineup_result(result)


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise NotFoundError("Invalid player id. Use the player_id returned by another tool.") from exc
